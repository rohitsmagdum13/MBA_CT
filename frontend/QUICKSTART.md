# Quick Start Guide - MBA Frontend

## Step-by-Step Instructions to Run the Frontend

### 1. Open Terminal in Frontend Directory

```bash
cd c:\Users\ROHIT\Work\HMA\MBA_CT\frontend
```

### 2. Install Dependencies (First Time Only)

```bash
npm install
```

This will install all required packages including:
- React
- Material-UI
- Testing libraries
- And other dependencies

**Note:** This step may take 3-5 minutes depending on your internet connection.

### 3. Start the Development Server

```bash
npm start
```

The application will automatically:
- Start on [http://localhost:3000](http://localhost:3000)
- Open in your default browser
- Hot-reload when you make changes

### 4. Verify Backend is Running

Make sure your FastAPI backend is running on `http://127.0.0.1:8000`

To start the backend (in a separate terminal):
```bash
cd c:\Users\ROHIT\Work\HMA\MBA_CT
python -m uvicorn src.MBA.api.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Common Commands

### Start Development Server
```bash
npm start
```

### Stop Development Server
Press `Ctrl + C` in the terminal

### Build for Production
```bash
npm run build
```

### Run Tests
```bash
npm test
```

### Check for Linting Issues
```bash
npm run lint
```

### Format Code
```bash
npm run format
```

---

## Troubleshooting

### Issue: Port 3000 is already in use

**Solution 1:** Kill the process using port 3000
```bash
# Find the process
netstat -ano | findstr :3000

# Kill it (replace <PID> with the actual process ID)
taskkill /PID <PID> /F
```

**Solution 2:** Use a different port
```bash
set PORT=3001
npm start
```

### Issue: npm install fails

**Solution:** Clear npm cache and retry
```bash
npm cache clean --force
npm install
```

### Issue: Cannot connect to backend

**Solution:** Verify backend is running and check the API URL in `.env` file:
```
REACT_APP_API_URL=http://127.0.0.1:8000
```

### Issue: CORS errors in browser console

**Solution:** Make sure your FastAPI backend has CORS middleware configured:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Project Structure

```
frontend/
├── public/              # Static files
│   ├── index.html      # HTML template
│   ├── manifest.json   # PWA manifest
│   └── robots.txt      # SEO robots file
├── src/                # Source code
│   ├── App.js          # Main application component
│   ├── DocumentViewer.js    # Document viewer component
│   ├── FeedbackControl.js   # Feedback component
│   ├── index.js        # Application entry point
│   ├── index.css       # Global styles
│   └── reportWebVitals.js   # Performance monitoring
├── .env                # Environment variables
├── package.json        # Dependencies and scripts
└── README.md          # Documentation
```

---

## Environment Variables

Edit `.env` file to configure:

```env
# Backend API URL
REACT_APP_API_URL=http://127.0.0.1:8000

# App Configuration
REACT_APP_APP_TITLE="HMA Agentic AI Assistants"

# Theme Colors
REACT_APP_PRIMARY_COLOR="#1976d2"
REACT_APP_SECONDARY_COLOR="#dc004e"
```

---

## Testing the Application

### 1. Test Member Benefit Inquiry
1. Open [http://localhost:3000](http://localhost:3000)
2. Enter a query like: "Is member M1001 active?"
3. Click "Check Member Benefits"
4. View the response

### 2. Test Document Upload
1. Click "Choose File" button
2. Select a PDF file
3. Click "Upload"
4. Check for success message

---

## Next Steps

1. **Customize Theme:** Edit colors in `.env` file
2. **Add Features:** Modify components in `src/` directory
3. **Deploy:** Run `npm run build` to create production bundle
4. **Test:** Run `npm test` to execute test suite

---

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the main [README.md](README.md)
3. Check backend logs for API errors
4. Review browser console for frontend errors

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `npm install` | Install dependencies |
| `npm start` | Start dev server |
| `npm test` | Run tests |
| `npm run build` | Create production build |
| `Ctrl + C` | Stop dev server |

---

**Happy Coding! 🚀**
