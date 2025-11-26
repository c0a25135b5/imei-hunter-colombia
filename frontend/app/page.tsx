'use client';
import { useState } from 'react';
import axios from 'axios';

export default function Home() {
  const [imei, setImei] = useState('');
  const [step, setStep] = useState(1);
  const [captchaImage, setCaptchaImage] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [captchaText, setCaptchaText] = useState('');
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  // Pythonサーバーへの接続
  const startCheck = async () => {
    if (!imei) return alert("IMEIを入力してください");
    // 数字15桁チェック
    if (!/^\d{15}$/.test(imei)) return alert("IMEIは15桁の数字のみです");

    setLoading(true);
    try {
      const res = await axios.get(`http://127.0.0.1:8000/start/${imei}`);
      setCaptchaImage(res.data.captcha_image);
      setSessionId(res.data.session_id);
      setStep(2);
    } catch (e: any) {
      const msg = e.response?.data?.detail || "通信エラーです。サーバーは動いていますか？";
      alert("エラー: " + msg);
    }
    setLoading(false);
  };

  const solveCheck = async () => {
    if (!captchaText) return alert("文字を入力してください");
    setLoading(true);
    try {
      const res = await axios.post(`http://127.0.0.1:8000/solve`, {
        session_id: sessionId,
        captcha_text: captchaText
      });
      setResult(res.data);
      if (res.data.status !== 'retry') {
        setStep(3);
      } else {
        alert("文字が違います。もう一度入力してください。");
        setCaptchaText(""); // 入力欄をクリア
      }
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message;
      alert("エラー: " + msg);
    }
    setLoading(false);
  };

  // ページリロード関数
  const resetApp = () => {
    setImei('');
    setStep(1);
    setResult(null);
    setCaptchaText('');
  };

  return (
    <div style={{ 
      minHeight: '100vh', 
      display: 'flex', 
      flexDirection: 'column', 
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
      background: '#f9f9f9'
    }}>
      
      {/* --- ヘッダー --- */}
      <header style={{ background: '#003399', padding: '15px 0', color: 'white', boxShadow: '0 2px 5px rgba(0,0,0,0.1)' }}>
        <div style={{ maxWidth: '500px', margin: '0 auto', padding: '0 20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '24px' }}>🇨🇴</span>
          <h1 style={{ margin: 0, fontSize: '20px', fontWeight: 'bold' }}>IMEI Hunter Colombia</h1>
        </div>
      </header>

      {/* --- メインコンテンツ --- */}
      <main style={{ flex: 1, padding: '20px' }}>
        <div style={{ maxWidth: '500px', margin: '0 auto', background: 'white', padding: '25px', borderRadius: '15px', boxShadow: '0 4px 15px rgba(0,0,0,0.05)' }}>
          
          {/* Step 1: 入力画面 */}
          {step === 1 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div style={{ textAlign: 'center' }}>
                <h2 style={{ margin: '0 0 10px 0', color: '#333' }}>IMEIチェック</h2>
                <p style={{ color: '#666', fontSize: '14px', margin: 0 }}>
                  中古スマホを買う前に、盗難品でないか確認しましょう。公式データベースと照合します。
                </p>
              </div>

              <div>
                <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '8px', color: '#444' }}>IMEI番号 (15桁)</label>
                <input 
                  type="tel" 
                  placeholder="例: 352012345678910" 
                  value={imei}
                  onChange={(e) => setImei(e.target.value)}
                  style={{ width: '100%', padding: '15px', fontSize: '18px', borderRadius: '8px', border: '1px solid #ccc', background: '#fafafa' }}
                />
              </div>

              <button 
                onClick={startCheck} 
                disabled={loading}
                style={{ 
                  width: '100%', padding: '16px', fontSize: '18px', fontWeight: 'bold',
                  background: loading ? '#ccc' : '#0070f3', 
                  color: 'white', border: 'none', borderRadius: '8px', cursor: loading ? 'wait' : 'pointer',
                  transition: '0.2s'
                }}
              >
                {loading ? 'サーバー通信中...' : '調査開始 (無料)'}
              </button>
            </div>
          )}

          {/* Step 2: CAPTCHA画面 */}
          {step === 2 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', textAlign: 'center' }}>
              <h3 style={{ margin: 0 }}>セキュリティチェック</h3>
              
              <div style={{ background: '#eee', padding: '15px', borderRadius: '8px', display: 'flex', justifyContent: 'center' }}>
                {captchaImage ? (
                  <img src={captchaImage} alt="captcha" style={{ borderRadius: '4px', height: '50px' }} />
                ) : (
                  <p>画像読み込み中...</p>
                )}
              </div>

              <input 
                type="text" 
                placeholder="画像に見える文字を入力" 
                value={captchaText}
                onChange={(e) => setCaptchaText(e.target.value)}
                style={{ width: '100%', padding: '15px', fontSize: '18px', borderRadius: '8px', border: '1px solid #ccc', textAlign: 'center' }}
              />

              <button 
                onClick={solveCheck} 
                disabled={loading}
                style={{ 
                  width: '100%', padding: '16px', fontSize: '18px', fontWeight: 'bold',
                  background: loading ? '#ccc' : '#28a745', 
                  color: 'white', border: 'none', borderRadius: '8px', cursor: loading ? 'wait' : 'pointer'
                }}
              >
                {loading ? '判定中...' : '結果を見る'}
              </button>
            </div>
          )}

          {/* Step 3: 結果画面（ビジネス導線あり） */}
          {step === 3 && result && (
            <div style={{ textAlign: 'center' }}>
              
              {/* 判定ヘッダー */}
              <div style={{ 
                padding: '20px', borderRadius: '10px', marginBottom: '20px',
                background: result.status === 'clean' ? '#d4edda' : '#f8d7da',
                color: result.status === 'clean' ? '#155724' : '#721c24',
                border: `1px solid ${result.status === 'clean' ? '#c3e6cb' : '#f5c6cb'}`
              }}>
                <h2 style={{ margin: '0 0 10px 0', fontSize: '24px' }}>
                  {result.status === 'clean' ? '✅ 安全です' : '❌ 危険！盗難品'}
                </h2>
                <p style={{ margin: 0, fontWeight: 'bold' }}>{result.message}</p>
              </div>

              {/* --- ビジネス導線エリア (ここが金脈！) --- */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                
                {/* パターンA: 安全だった場合 */}
                {result.status === 'clean' && (
                  <>
                    <p style={{ fontSize: '14px', color: '#666', margin: '5px 0' }}>
                      このスマホは問題ありません。<br/>高値で売りたいですか？それとも盗難保険に入りますか？
                    </p>
                    
                    {/* 導線1: 買取査定 (WhatsAppへ) */}
                    <a 
                      href="https://wa.me/573001234567?text=Hola,%20quiero%20vender%20mi%20celular" 
                      target="_blank"
                      style={{
                        display: 'block', padding: '15px', borderRadius: '8px',
                        background: '#25D366', color: 'white', textDecoration: 'none', fontWeight: 'bold'
                      }}
                    >
                      📱 このスマホを査定する (WhatsApp)
                    </a>

                    {/* 導線2: 保険アフィリエイト (ダミーリンク) */}
                    <a 
                      href="https://www.segurosbolivar.com/" 
                      target="_blank"
                      style={{
                        display: 'block', padding: '15px', borderRadius: '8px',
                        background: 'white', color: '#003399', textDecoration: 'none', fontWeight: 'bold',
                        border: '2px solid #003399'
                      }}
                    >
                      🛡️ 盗難保険を見る (月額$3〜)
                    </a>
                  </>
                )}

                {/* パターンB: 危険だった場合 */}
                {(result.status === 'stolen' || result.status === 'unknown') && (
                  <>
                    <p style={{ fontSize: '14px', color: '#666', margin: '5px 0' }}>
                      このスマホを買うのは危険です！<br/>保証付きの安全な端末を探しましょう。
                    </p>
                    
                    {/* 導線3: 中古販売アフィリエイト (MercadoLibreへ) */}
                    <a 
                      href="https://listado.mercadolibre.com.co/celulares-telefonos/" 
                      target="_blank"
                      style={{
                        display: 'block', padding: '15px', borderRadius: '8px',
                        background: '#FFE600', color: '#2D3277', textDecoration: 'none', fontWeight: 'bold',
                        boxShadow: '0 2px 5px rgba(0,0,0,0.1)'
                      }}
                    >
                      🛍️ MercadoLibreで安全なスマホを探す
                    </a>
                  </>
                )}

              </div>

              <button 
                onClick={resetApp}
                style={{ marginTop: '30px', background: 'none', border: 'none', color: '#666', textDecoration: 'underline', cursor: 'pointer' }}
              >
                別の番号を調べる
              </button>
            </div>
          )}

        </div>
      </main>

      {/* --- フッター --- */}
      <footer style={{ textAlign: 'center', padding: '20px', color: '#999', fontSize: '12px' }}>
        <p>© 2025 IMEI Hunter Colombia. All rights reserved.</p>
        <p>Data provided by SRTM Colombia.</p>
      </footer>
    </div>
  );
}