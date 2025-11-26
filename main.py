from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import re
import uuid
import time

# --- グローバル変数（Chromeをここに保持する） ---
shared_driver = None

# --- 起動時・終了時の処理（ライフサイクル） ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global shared_driver
    print(">>> サーバー起動: Chromeを立ち上げます...")
    
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # ページ読み込みを「全部待たない（eager）」設定にして高速化
    options.page_load_strategy = 'eager' 
    
    # Render上のChromeパス
    chrome_binary_path = "/opt/render/project/.render/chrome/opt/google/chrome/chrome"
    if os.path.exists(chrome_binary_path):
        options.binary_location = chrome_binary_path

    # 画像ブロック
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    
    # ★ここで起動！（1回だけ）
    shared_driver = webdriver.Chrome(service=Service(), options=options)
    
    yield # ここでアプリが動き続ける
    
    print(">>> サーバー終了: Chromeを閉じます...")
    shared_driver.quit()

app = FastAPI(lifespan=lifespan)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SolveRequest(BaseModel):
    session_id: str # 今回は使い回すのでIDでの管理は簡易化しますが、互換性のため残します
    captcha_text: str

# --- 1. セッション開始 ---
@app.get("/start/{imei}")
def start_check(imei: str):
    if not re.fullmatch(r"\d{15}", imei):
        raise HTTPException(status_code=400, detail="IMEIは15桁の数字で入力してください")

    global shared_driver
    driver = shared_driver
    
    try:
        print(f">>> {imei} の調査開始")
        url = "https://www.imeicolombia.com.co/"
        driver.get(url)
        
        # 待ち時間を短縮
        wait = WebDriverWait(driver, 5) 
        
        imei_input = wait.until(EC.presence_of_element_located((By.NAME, "IMEI")))
        imei_input.clear()
        imei_input.send_keys(imei)

        canvas = wait.until(EC.presence_of_element_located((By.ID, "captcha")))
        canvas_png = canvas.screenshot_as_base64
        
        # 使い回すので session_id はダミーでもOKだが、一応発行
        session_id = str(uuid.uuid4())
        
        return {
            "session_id": session_id,
            "captcha_image": "data:image/png;base64," + canvas_png
        }

    except Exception as e:
        print(f"エラー: {e}")
        # エラー時はリフレッシュして復帰を試みる
        try: driver.refresh() 
        except: pass
        raise HTTPException(status_code=500, detail="サイト接続エラー。もう一度試してください。")

# --- 2. 判定実行 ---
@app.post("/solve")
def solve_captcha(request: SolveRequest):
    text = request.captcha_text
    print(f">>> 文字受信: {text}")
    
    global shared_driver
    driver = shared_driver
    wait = WebDriverWait(driver, 10)
    
    try:
        captcha_input = driver.find_element(By.ID, "txtInput")
        captcha_input.send_keys(text)

        search_button = driver.find_element(By.ID, "buscar")
        search_button.click()
        
        # ★修正: 結果が表示されるまで確実に待つ！
        # "Resultado de la consulta"（結果）という文字が出るか、テーブルが出るのを待つ
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, "//td[contains(text(), 'IMEI')]")))
        except:
            # タイムアウトした場合（CAPTCHAミスなどの可能性）
            pass

        # 画面全体の文字を取得
        page_text = driver.find_element(By.TAG_NAME, "body").text
        
        result = {}
        
        # 判定ロジック（誤検知を防ぐため、条件を厳しくする）
        if "no se encuentra registrado" in page_text:
            result = {"status": "clean", "message": "✅ 安全！盗難届は出ていません。"}
        
        # ★修正: 判定の優先順位を変更！
        # 1. まず「キャプチャミス」を疑う（最優先）
        if "Captcha ingresado incorrecto" in page_text or "incorrecto" in page_text.lower():
            result = {"status": "retry", "message": "⚠️ 画像の文字が違います。"}
        
        # 2. 次に「安全」を確認
        elif "no se encuentra registrado" in page_text:
            result = {"status": "clean", "message": "✅ 安全！盗難届は出ていません。"}
        
        # 3. 最後に「危険」を確認（誤爆を防ぐため条件を厳しく）
        # "se encuentra reportado" があり、かつ "no se encuentra" がない場合のみ黒とみなす
        elif "se encuentra reportado" in page_text and "no se encuentra" not in page_text:
            result = {"status": "stolen", "message": "❌ 危険！盗難届が出ています。"}
            
        else:
            # それでもわからなければ、キャプチャミスとみなして再トライさせる方が安全
            # result = {"status": "unknown", "message": "❓ 解析不能"} 
            # ↓ 変更
            result = {"status": "retry", "message": "⚠️ 読み取れませんでした。もう一度試してください。"}

        return result

    except Exception as e:
        print(f"エラー: {e}")
        # エラー時はブラウザをリセットして次の人のために綺麗にする
        try: 
            driver.get("https://www.imeicolombia.com.co/")
        except: 
            pass
        raise HTTPException(status_code=500, detail="判定エラー")
    
    finally:
        # 次の人のためにページをリセットしておく等は今回は省略（getで上書きされるので）
        pass