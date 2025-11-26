from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fastapi.middleware.cors import CORSMiddleware
import re
import uuid
import os

app = FastAPI()

# CORS設定（本番では特定のドメインのみに絞るのがベスト）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # 自分のPCでのテスト用
        "https://imei-hunter-colombia.vercel.app", # ★Vercelの本番URLを追加！
        "*" # 念のためワイルドカードも残しておくが、上の明示指定が効くはず
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 起動中のブラウザを一時保存
active_drivers = {}

# リクエストデータの定義
class SolveRequest(BaseModel):
    session_id: str
    captcha_text: str

def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # ★追加: クラウド(Render)上のChromeの場所を指定
    chrome_binary_path = "/opt/render/project/.render/chrome/opt/google/chrome/chrome"
    if os.path.exists(chrome_binary_path):
        options.binary_location = chrome_binary_path

    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(service=Service(), options=options)
    return driver

# --- 1. セッション開始 ---
@app.get("/start/{imei}")
def start_check(imei: str):
    # ★セキュリティ: 入力チェック（数字15桁以外は即弾く）
    if not re.fullmatch(r"\d{15}", imei):
        raise HTTPException(status_code=400, detail="IMEIは15桁の数字で入力してください")

    print(f">>> セッション開始: IMEI {imei}")
    session_id = str(uuid.uuid4())
    
    driver = get_driver()
    
    try:
        url = "https://www.imeicolombia.com.co/"
        driver.get(url)
        
        # ★高速化: time.sleepをやめて、入力欄が出るまで「最大10秒」待つ（出たら0.1秒で進む）
        wait = WebDriverWait(driver, 10)
        
        # IMEI入力欄が見つかるまで待機
        imei_input = wait.until(EC.presence_of_element_located((By.NAME, "IMEI")))
        imei_input.clear()
        imei_input.send_keys(imei)

        # CAPTCHA画像が見つかるまで待機
        canvas = wait.until(EC.presence_of_element_located((By.ID, "captcha")))
        canvas_png = canvas.screenshot_as_base64
        
        active_drivers[session_id] = driver
        
        return {
            "session_id": session_id,
            "captcha_image": "data:image/png;base64," + canvas_png
        }

    except Exception as e:
        driver.quit()
        print(f"エラー: {e}")
        raise HTTPException(status_code=500, detail="サイトへの接続に失敗しました")

# --- 2. 判定実行 ---
@app.post("/solve")
def solve_captcha(request: SolveRequest):
    session_id = request.session_id
    text = request.captcha_text
    
    print(f">>> 文字受信: {text} (Session: {session_id})")
    
    if session_id not in active_drivers:
        raise HTTPException(status_code=400, detail="セッション切れです。最初からやり直してください。")
    
    driver = active_drivers[session_id]
    wait = WebDriverWait(driver, 10)
    
    try:
        # 文字入力
        captcha_input = driver.find_element(By.ID, "txtInput")
        captcha_input.send_keys(text)

        # 検索ボタンを押す
        search_button = driver.find_element(By.ID, "buscar")
        search_button.click()
        
        # ★高速化: 結果の文字が表示されるまで待つ（bodyタグ内の変化を監視）
        # ここは少し難しいですが、とりあえず「bodyが読み込まれる」のを待つ形にします
        # 厳密には「結果テーブル」が表示されるのを待つのがベスト
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))

        # 結果取得
        page_text = driver.find_element(By.TAG_NAME, "body").text
        
        result = {}
        if "no se encuentra registrado" in page_text:
            result = {"status": "clean", "message": "✅ 安全！盗難届は出ていません。"}
        elif "se encuentra reportado" in page_text:
            result = {"status": "stolen", "message": "❌ 危険！盗難届が出ています。"}
        elif "Captcha ingresado incorrecto" in page_text:
            result = {"status": "retry", "message": "⚠️ 画像の文字が違います。"}
        else:
            result = {"status": "unknown", "message": "❓ 解析不能"}

        return result

    except Exception as e:
        print(f"エラー: {e}")
        raise HTTPException(status_code=500, detail="判定中にエラーが発生しました")
    
    finally:
        driver.quit()
        if session_id in active_drivers:
            del active_drivers[session_id]