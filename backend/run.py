import uvicorn
import os

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    reload_flag = os.getenv("RELOAD", "false").lower() in ("true", "1")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, workers=1, reload=reload_flag)
