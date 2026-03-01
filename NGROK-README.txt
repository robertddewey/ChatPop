ngrok Quick Reference
====================

Start tunnel (with static domain):
  ngrok http https://localhost:4000 --url=YOUR-DOMAIN.ngrok-free.app

Start tunnel (without static domain):
  ngrok http https://localhost:4000

Get a free static domain:
  https://dashboard.ngrok.com/cloud-edge/domains

Configure your domain in backend/.env:
  NGROK_DOMAIN=your-subdomain.ngrok-free.app

Note: The frontend server (port 4000) must be running before starting ngrok.
See README.md for full setup instructions.
