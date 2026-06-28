export default async function handler(req, res) {
  const target = 'https://gaokao-api-274470-6-1443956945.sh.run.tcloudbase.com';
  const url = new URL(req.url, target);
  const resp = await fetch(url, {
    method: req.method,
    headers: { 'Content-Type': 'application/json' },
    body: req.method === 'GET' ? undefined : JSON.stringify(req.body),
  });
  const data = await resp.json();
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.status(resp.status).json(data);
}