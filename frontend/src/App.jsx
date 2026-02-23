import { Routes, Route, Link } from 'react-router-dom';
import ArticleList from './pages/ArticleList';
import ArticleDetail from './pages/ArticleDetail';
import FetchTrigger from './pages/FetchTrigger';

export default function App() {
  return (
    <div className="app">
      <nav className="navbar">
        <Link to="/" className="nav-brand">News Summarizer</Link>
        <div className="nav-links">
          <Link to="/">Articles</Link>
          <Link to="/fetch">Fetch Articles</Link>
        </div>
      </nav>
      <main className="container">
        <Routes>
          <Route path="/" element={<ArticleList />} />
          <Route path="/articles/:id" element={<ArticleDetail />} />
          <Route path="/fetch" element={<FetchTrigger />} />
        </Routes>
      </main>
    </div>
  );
}
