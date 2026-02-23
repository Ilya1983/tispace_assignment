import { useState } from 'react';
import { triggerFetch } from '../api';

export default function FetchTrigger() {
  const [keyword, setKeyword] = useState('markets');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleFetch = () => {
    setLoading(true);
    setError(null);
    setResult(null);
    triggerFetch(keyword)
      .then(setResult)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  return (
    <div>
      <h1 style={{ marginBottom: '1rem' }}>Fetch Articles</h1>
      <div className="card">
        <p style={{ marginBottom: '1rem' }}>
          Trigger a fetch from the Marketaux API. Articles are deduplicated automatically.
        </p>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="Search keyword"
          />
          <button onClick={handleFetch} disabled={loading || !keyword.trim()}>
            {loading ? 'Fetching...' : 'Fetch Now'}
          </button>
        </div>

        {error && <p className="error">{error}</p>}

        {result && (
          <div className="result-box">
            <p><strong>Fetched:</strong> {result.fetched} new articles</p>
            <p><strong>Skipped:</strong> {result.skipped} (already in database)</p>
            <p><strong>Failed:</strong> {result.failed}</p>
          </div>
        )}
      </div>
    </div>
  );
}
