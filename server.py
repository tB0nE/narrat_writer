import os
import uvicorn
from dotenv import load_dotenv
from src.server.api import app

# Load environment variables
load_dotenv()

if __name__ == "__main__":
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 8045))
    
    # Run the modularized FastAPI app
    uvicorn.run(app, host=host, port=port)
