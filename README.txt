STOP the old API (Ctrl+C), then:

1. Copy fix2/backend/app/* into your backend/app/
2. Copy fix2/portal/index.html into portal/ AND backend/portal/
3. Restart:
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level debug

4. Open http://127.0.0.1:8000/docs
   - Try POST /v1/echo  (must return {"ok":true} in <1s)
   - Try POST /v1/procedures

5. Portal: http://127.0.0.1:8000/portal/
   - Click "Test POST /v1/echo"
   - Then Save & publish

If /v1/echo also times out, the problem is not procedures code (firewall/proxy/browser).
