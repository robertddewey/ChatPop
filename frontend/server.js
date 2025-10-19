const { createServer } = require('https');
const { parse } = require('url');
const next = require('next');
const fs = require('fs');
const path = require('path');
const http = require('http');
const https = require('https');

const dev = process.env.NODE_ENV !== 'production';
const hostname = '0.0.0.0';
const port = 4000;
const backendUrl = 'https://localhost:9000';

// IMPORTANT: Proxy is only needed in development
// In production, use ALB path-based routing instead:
//   /api/* → Backend target group
//   /media/* → Backend target group
//   /ws/* → Backend target group (WebSocket)
//   /* → Frontend target group
const ENABLE_PROXY = dev;

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
    rejectUnauthorized: false, // Accept self-signed certificates
  };

  const proxyReq = https.request(options, (proxyRes) => {
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

// Proxy WebSocket upgrade requests to Django backend
function proxyWebSocket(req, socket, head) {
  const options = {
    hostname: 'localhost',
    port: 9000,
    path: req.url,
    method: req.method,
    headers: req.headers,
    rejectUnauthorized: false, // Accept self-signed certificates
  };

  console.log('[WebSocket Proxy] Upgrading connection:', req.url);

  const proxyReq = https.request(options);

  proxyReq.on('upgrade', (proxyRes, proxySocket, proxyHead) => {
    console.log('[WebSocket Proxy] Backend upgrade successful');
    socket.write('HTTP/1.1 101 Switching Protocols\r\n');
    Object.keys(proxyRes.headers).forEach((key) => {
      socket.write(`${key}: ${proxyRes.headers[key]}\r\n`);
    });
    socket.write('\r\n');

    if (proxyHead.length > 0) {
      socket.write(proxyHead);
    }

    proxySocket.pipe(socket);
    socket.pipe(proxySocket);

    proxySocket.on('error', (err) => {
      console.error('[WebSocket Proxy] Backend socket error:', err);
      socket.destroy();
    });

    socket.on('error', (err) => {
      console.error('[WebSocket Proxy] Client socket error:', err);
      proxySocket.destroy();
    });
  });

  proxyReq.on('error', (err) => {
    console.error('[WebSocket Proxy] Upgrade error:', err);
    socket.destroy();
  });

  proxyReq.end();
}

app.prepare().then(() => {
  const server = createServer(httpsOptions, async (req, res) => {
    try {
      const parsedUrl = parse(req.url, true);

      // Proxy API and media requests to Django backend (development only)
      // In production, ALB handles this routing
      if (ENABLE_PROXY && (parsedUrl.pathname.startsWith('/api/') ||
          parsedUrl.pathname.startsWith('/media/'))) {
        proxyRequest(req, res);
      } else {
        await handle(req, res, parsedUrl);
      }
    } catch (err) {
      console.error('Error occurred handling', req.url, err);
      res.statusCode = 500;
      res.end('internal server error');
    }
  });

  // Handle WebSocket upgrade requests (development only)
  // In production, ALB handles WebSocket routing
  if (ENABLE_PROXY) {
    server.on('upgrade', (req, socket, head) => {
      const parsedUrl = parse(req.url, true);

      // Proxy WebSocket connections to Django backend
      if (parsedUrl.pathname.startsWith('/ws/')) {
        proxyWebSocket(req, socket, head);
      } else {
        socket.destroy();
      }
    });
  }

  server.once('error', (err) => {
    console.error(err);
    process.exit(1);
  });

  server.listen(port, () => {
    console.log(`> Ready on https://${hostname}:${port}`);
    console.log(`> Access via https://localhost:${port} or https://10.0.0.135:${port}`);
    if (ENABLE_PROXY) {
      console.log(`> Proxying /api/, /media/, /ws/ to ${backendUrl}`);
      console.log(`> WebSocket connections are proxied through this server`);
    } else {
      console.log(`> Production mode: Expecting ALB to handle /api/, /media/, /ws/ routing`);
    }
  });
});
