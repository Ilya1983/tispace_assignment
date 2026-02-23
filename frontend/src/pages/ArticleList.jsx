import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { fetchArticles } from '../api';

export default function ArticleList() {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const pageSize = 10;

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchArticles(page, pageSize)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [page]);

  if (loading) return <p className="loading">Loading articles...</p>;
  if (error) return <p className="error">{error}</p>;
  if (!data || data.results.length === 0) {
    return (
      <div className="card">
        <p>No articles yet. <Link to="/fetch">Fetch some articles</Link> first.</p>
      </div>
    );
  }

  const totalPages = Math.ceil(data.total / pageSize);

  return (
    <div>
      <h1 style={{ marginBottom: '1rem' }}>Articles ({data.total})</h1>
      {data.results.map((article) => (
        <div className="card" key={article.id}>
          <h2>
            <Link to={`/articles/${article.id}`}>{article.title}</Link>
          </h2>
          <div className="meta">
            {article.source} &middot;{' '}
            {article.published_at
              ? new Date(article.published_at).toLocaleDateString()
              : 'Unknown date'}
          </div>
          {article.description && <p>{article.description}</p>}
        </div>
      ))}
      <div className="pagination">
        <button disabled={page <= 1} onClick={() => setPage(page - 1)}>
          Previous
        </button>
        <span>
          Page {page} of {totalPages}
        </span>
        <button disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
          Next
        </button>
      </div>
    </div>
  );
}
