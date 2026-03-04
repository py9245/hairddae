import './App.css'
import env from './config/env'

function App() {
  const appName = env.appName

  return (
    <main className="page">
      <p className="tag">{appName}</p>
      <h1 className="title">홈입니다</h1>
      <p className="subtitle">최소한의 시작 화면을 준비했어요.</p>
    </main>
  )
}

export default App
