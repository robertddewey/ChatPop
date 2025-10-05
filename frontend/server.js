const { createServer } = require('https');
const { parse } = require('url');
const next = require('next');
const fs = require('fs');
const path = require('path');
const http = require('http');

const dev = process.env.NODE_ENV !== 'production';
const hostname = '0.0.0.0';
const port = 4000;
const backendUrl = 'http://localhost:9000';

const app = next({ dev, hostname, port });
const handle = app.getRequestHandler();

const httpsOptions = {
  key: fs.readFileSync(path.join(__dirname, '..', 'certs', 'localhost+3-key.pem')),
  cert: fs.readFileSync(path.join(__dirname, '..', 'certs', 'localhost+3.pem')),
};

// Proxy function to forward API requests to Django backend
function proxyRequest(req, res) {
  const options = {
    hostname: 'localhost',
    port: 9000,
    path: req.url,
    method: req.method,
    headers: req.headers,
  };

  const proxyReq = http.request(options, (proxyRes) => {
    res.writeHead(proxyRes.statusCode, proxyRes.headers);
    proxyRes.pipe(res, { end: true });
  });

  req.pipe(proxyReq, { end: true });

  proxyReq.on('error', (err) => {
    console.error('Proxy error:', err);
    res.statusCode = 502;
    res.end('Bad Gateway');
  });
}

app.prepare().then(() => {
  createServer(httpsOptions, async (req, res) => {
    try {
      const parsedUrl = parse(req.url, true);

      // Proxy API and media requests to Django backend over HTTP
      if (parsedUrl.pathname.startsWith('/api/') ||
          parsedUrl.pathname.startsWith('/media/')) {
        proxyRequest(req, res);
      } else {
        await handle(req, res, parsedUrl);
      }
    } catch (err) {
      console.error('Error occurred handling', req.url, err);
      res.statusCode = 500;
      res.end('internal server error');
    }
  })
    .once('error', (err) => {
      console.error(err);
      process.exit(1);
    })
    .listen(port, () => {
      console.log(`> Ready on https://${hostname}:${port}`);
      console.log(`> Access via https://localhost:${port} or https://10.0.0.135:${port}`);
      console.log(`> Proxying /api/, /media/ to ${backendUrl}`);
      console.log(`> Note: WebSocket connections will use HTTP backend at ${backendUrl}`);
    });
});
