import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchArticle, fetchSummary } from '../api';

export default function ArticleDetail() {
  const { id } = useParams();
  const [article, setArticle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState(null);

  useEffect(() => {
    setLoading(true);
    fetchArticle(id)
      .then(setArticle)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  const handleSummary = () => {
    setSummaryLoading(true);
    setSummaryError(null);
    fetchSummary(id)
      .then(setSummary)
      .catch((e) => setSummaryError(e.message))
      .finally(() => setSummaryLoading(false));
  };

  if (loading) return <p className="loading">Loading article...</p>;
  if (error) return <p className="error">{error}</p>;
  if (!article) return <p className="error">Article not found</p>;

  return (
    <div>
      <Link to="/" className="back-link">&larr; Back to articles</Link>
      <div className="card">
        <h1>{article.title}</h1>
        <div className="meta">
          {article.source} &middot;{' '}
          {article.published_at
            ? new Date(article.published_at).toLocaleDateString()
            : 'Unknown date'}
          {' '}&middot;{' '}
          <a href={article.url} target="_blank" rel="noopener noreferrer">
            Original article
          </a>
        </div>

        {article.content ? (
          <div className="article-content">{article.content}</div>
        ) : (
          <p style={{ marginTop: '1rem', color: '#888' }}>
            No content available (scraping failed).
          </p>
        )}
      </div>

      <div className="card">
        <h2>AI Summary</h2>
        <button onClick={handleSummary} disabled={summaryLoading || !article.content}>
          {summaryLoading ? 'Generating...' : 'Generate Summary'}
        </button>

        {summaryLoading && <p className="loading" style={{ marginTop: '0.5rem' }}>Calling Claude Haiku 4.5 — this may take a few seconds...</p>}
        {summaryError && <p className="error">{summaryError}</p>}

        {summary && (
          <div className="summary-box">
            <p>{summary.summary}</p>
            <span className={`cached-badge ${summary.cached ? 'hit' : 'miss'}`}>
              {summary.cached ? 'Cached' : 'Fresh'}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
