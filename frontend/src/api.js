const BASE = '';

export async function fetchArticles(page = 1, pageSize = 20) {
  const res = await fetch(`${BASE}/articles?page=${page}&page_size=${pageSize}`);
  if (!res.ok) throw new Error(`Failed to fetch articles: ${res.status}`);
  return res.json();
}

export async function fetchArticle(id) {
  const res = await fetch(`${BASE}/articles/${id}`);
  if (!res.ok) throw new Error(`Failed to fetch article: ${res.status}`);
  return res.json();
}

export async function fetchSummary(id) {
  const res = await fetch(`${BASE}/articles/${id}/summary`);
  if (res.status === 422) throw new Error('Article has no content to summarize');
  if (!res.ok) throw new Error(`Failed to fetch summary: ${res.status}`);
  return res.json();
}

export async function triggerFetch(keyword = 'markets') {
  const res = await fetch(`${BASE}/articles/fetch?keyword=${encodeURIComponent(keyword)}`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed to trigger fetch: ${res.status}`);
  return res.json();
}
