# MBA Frontend - Member Benefit Assistant

React-based frontend for the Member Benefit AI Assistant application.

## Prerequisites

- Node.js (v16 or higher)
- npm (v8 or higher)

## Installation

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

## Running the Application

### Development Mode

Start the development server:
```bash
npm start
```

The application will open at [http://localhost:3000](http://localhost:3000)

### Production Build

Create an optimized production build:
```bash
npm run build
```

The build files will be in the `build/` directory.

## Available Scripts

- `npm start` - Runs the app in development mode
- `npm test` - Launches the test runner
- `npm run build` - Builds the app for production
- `npm run lint` - Runs ESLint on source files
- `npm run format` - Formats code with Prettier

## Environment Variables

Create a `.env` file in the frontend directory with:

```
REACT_APP_API_URL=http://127.0.0.1:8000
REACT_APP_APP_TITLE="HMA Agentic AI Assistants"
```

## API Endpoints

The frontend connects to the FastAPI backend at:
- Default: `http://127.0.0.1:8000`
- Orchestration endpoint: `/orchestrate/query`
- Upload endpoints: `/upload/single`, `/upload/multi`

## Features

- Member benefit inquiry interface
- Document upload functionality
- Real-time query processing
- Material-UI components
- Responsive design

## Troubleshooting

### Port 3000 already in use
```bash
# Kill the process using port 3000 (Windows)
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# Or use a different port
set PORT=3001 && npm start
```

### CORS Issues
Make sure your FastAPI backend has CORS middleware configured to allow requests from `http://localhost:3000`
