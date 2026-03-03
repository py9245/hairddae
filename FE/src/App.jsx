import './App.css'

function App() {
  const appName = import.meta.env.VITE_APP_NAME || 'S14P21M101 · FE'

  return (
    <main className="page">
      <p className="tag">{appName}</p>
      <h1 className="title">홈입니다</h1>
      <p className="subtitle">최소한의 시작 화면을 준비했어요.</p>
    </main>
  )
}

export default App
