import React, { useState } from 'react';
import {
  Box, Container, Typography, TextField, Button, CircularProgress, Paper,
  ThemeProvider, createTheme, Alert, Stack, Chip, Tooltip, Tabs, Tab,
  Card, CardContent, Divider, LinearProgress
} from '@mui/material';
import {
  AccessTime, MedicalInformation, Receipt, UploadFile, CheckCircle,
  Send, AutoAwesome, CloudUpload, Description
} from '@mui/icons-material';


const theme = createTheme({
  palette: {
    primary: { main: '#1976d2' },
    secondary: { main: '#dc004e' },
    success: { main: '#2e7d32' },
    background: { default: '#f5f9fc' },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    h4: { fontWeight: 600, color: '#2c3e50' },
  },
});

const ExecutionTimeBadge = ({ time }) => (
  <Tooltip title="API Execution Time">
    <Chip
      icon={<AccessTime fontSize="small" />}
      label={`${(time / 1000).toFixed(2)}s`}
      size="small"
      color="info"
      variant="outlined"
      sx={{ ml: 1, fontFamily: 'monospace' }}
    />
  </Tooltip>
);

const App = () => {
  const [activeTab, setActiveTab] = useState(0);

  // Query state
  const [inputQuery, setInputQuery] = useState('');
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [metrics, setMetrics] = useState({ startTime: null, endTime: null, duration: null });

  // Upload state
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [documentReady, setDocumentReady] = useState(false);

  const handleTabChange = (event, newValue) => {
    setActiveTab(newValue);
    // Reset states when switching tabs
    setError(null);
    setResponse(null);
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      setUploadStatus(null);
      setDocumentReady(false);
      setError(null);
    }
  };

  const handleFileUpload = async () => {
    if (!selectedFile) {
      setUploadStatus({ severity: 'warning', message: 'Please select a file to upload.' });
      return;
    }

    // Validate file type
    const fileExtension = selectedFile.name.toLowerCase().split('.').pop();
    if (!['pdf', 'csv'].includes(fileExtension)) {
      setUploadStatus({
        severity: 'error',
        message: 'Only PDF and CSV files are supported.'
      });
      return;
    }

    setUploadLoading(true);
    setUploadProgress(0);
    setUploadStatus(null);
    setDocumentReady(false);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      // Choose endpoint based on file type
      let endpoint;
      if (fileExtension === 'pdf') {
        // PDF files go through RAG preparation
        endpoint = `${process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000'}/rag/upload-and-prepare`;
      } else if (fileExtension === 'csv') {
        // CSV files go to single upload
        endpoint = `${process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000'}/upload/single`;
      }

      setUploadProgress(30);

      const res = await fetch(endpoint, {
        method: 'POST',
        body: formData,
      });

      setUploadProgress(70);

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || `Upload failed with status ${res.status}`);
      }

      const data = await res.json();
      setUploadProgress(100);

      if (fileExtension === 'pdf') {
        // PDF with RAG preparation response
        if (data.success && data.query_ready) {
          setUploadStatus({
            severity: 'success',
            message: `PDF uploaded and indexed successfully! ${data.rag_preparation?.chunks_count || 0} chunks created.`,
            details: data
          });
          setDocumentReady(true);
        } else if (data.success === false && data.error) {
          // Textract not ready - show helpful message
          setUploadStatus({
            severity: 'warning',
            message: `PDF uploaded to S3, but Textract processing is not configured. The PDF has been saved at: ${data.s3_uri}. To use RAG features, you need to: 1) Set up AWS Textract Lambda trigger, or 2) Process PDFs manually and use the /rag/prepare endpoint with the Textract output location.`,
            details: data
          });
        } else {
          setUploadStatus({
            severity: 'warning',
            message: data.message || 'PDF uploaded but RAG preparation incomplete.',
            details: data
          });
        }
      } else if (fileExtension === 'csv') {
        // CSV upload response
        setUploadStatus({
          severity: 'success',
          message: `File uploaded successfully! S3 URI: ${data.s3_uri}`,
          details: data
        });
        setDocumentReady(true);
      }

    } catch (err) {
      setUploadStatus({
        severity: 'error',
        message: err.message || 'File upload failed.'
      });
    } finally {
      setUploadLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputQuery.trim()) {
      setError('Please enter a valid query');
      return;
    }

    setLoading(true);
    setError(null);
    setResponse(null);
    const start = performance.now();
    setMetrics({ startTime: new Date().toISOString(), endTime: null, duration: null });

    try {
      // Call orchestration endpoint
      const res = await fetch(`${process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000'}/orchestrate/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: inputQuery.trim(),
          context: {},
          preserve_history: false
        })
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || `Request failed with status ${res.status}`);
      }

      const data = await res.json();

      // Process orchestration response
      if (data.success) {
        setResponse({
          success: true,
          intent: data.intent,
          confidence: data.confidence,
          agent: data.agent,
          result: data.result,
          reasoning: data.reasoning,
          entities: data.extracted_entities,
          rawData: data
        });
      } else {
        setError(data.error || 'No valid response from orchestrator');
      }
    } catch (err) {
      setError(err.message || 'Failed to fetch response');
    } finally {
      const end = performance.now();
      setMetrics(prev => ({
        ...prev,
        endTime: new Date().toISOString(),
        duration: end - start
      }));
      setLoading(false);
    }
  };

  const formatResultData = (result) => {
    if (!result) return 'No data available';

    // Handle string results
    if (typeof result === 'string') return result;

    // Handle object results with pretty formatting
    if (typeof result === 'object') {
      // Special formatting for different result types
      if (result.valid !== undefined) {
        // Member verification result
        return (
          <Box>
            <Typography variant="body1" gutterBottom>
              <strong>Member Valid:</strong> {result.valid ? 'Yes' : 'No'}
            </Typography>
            {result.member_id && (
              <Typography variant="body2">
                <strong>Member ID:</strong> {result.member_id}
              </Typography>
            )}
            {result.name && (
              <Typography variant="body2">
                <strong>Name:</strong> {result.name}
              </Typography>
            )}
            {result.dob && (
              <Typography variant="body2">
                <strong>Date of Birth:</strong> {result.dob}
              </Typography>
            )}
            {result.message && (
              <Typography variant="body2" color="text.secondary">
                {result.message}
              </Typography>
            )}
          </Box>
        );
      } else if (result.found !== undefined) {
        // Benefit/Deductible lookup result
        return (
          <Box>
            <Typography variant="body1" gutterBottom>
              <strong>Found:</strong> {result.found ? 'Yes' : 'No'}
            </Typography>
            {result.benefits && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2" gutterBottom>Benefits:</Typography>
                {result.benefits.map((benefit, idx) => (
                  <Card key={idx} variant="outlined" sx={{ mb: 1, p: 1 }}>
                    <Typography variant="body2">
                      <strong>{benefit.service || benefit.benefit_type}:</strong> {benefit.allowed_limit || benefit.limit}
                    </Typography>
                    {benefit.used !== undefined && (
                      <Typography variant="body2">
                        Used: {benefit.used} | Remaining: {benefit.remaining || 'N/A'}
                      </Typography>
                    )}
                  </Card>
                ))}
              </Box>
            )}
            {result.individual && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2">Individual Deductible:</Typography>
                <Typography variant="body2">{JSON.stringify(result.individual, null, 2)}</Typography>
              </Box>
            )}
            {result.message && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {result.message}
              </Typography>
            )}
          </Box>
        );
      } else if (result.answer) {
        // RAG answer result
        return (
          <Box>
            <Typography variant="body1" paragraph>
              {result.answer}
            </Typography>
            {result.sources && result.sources.length > 0 && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2" gutterBottom>Sources:</Typography>
                {result.sources.map((source, idx) => (
                  <Card key={idx} variant="outlined" sx={{ mb: 1, p: 1 }}>
                    <Typography variant="caption" color="text.secondary">
                      Source {source.source_id || idx + 1}
                    </Typography>
                    <Typography variant="body2">
                      {source.content?.substring(0, 200)}...
                    </Typography>
                  </Card>
                ))}
              </Box>
            )}
          </Box>
        );
      }

      // Fallback to JSON display
      return JSON.stringify(result, null, 2);
    }

    return String(result);
  };
  const renderMemberBenefitTab = () => (
    <Paper sx={{ p: 3, mb: 3 }}>
      {/* Upload Section */}
      <Card variant="outlined" sx={{ mb: 3, p: 2, bgcolor: '#f8f9fa' }}>
        <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2 }}>
          <CloudUpload color="primary" />
          <Typography variant="h6">Step 1: Upload Document (Optional)</Typography>
        </Stack>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Upload a CSV data file to add member/benefit data. (Note: PDF upload requires AWS Textract configuration)
        </Typography>

        <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
          <Button
            variant="outlined"
            component="label"
            startIcon={<UploadFile />}
            disabled={uploadLoading}
          >
            {selectedFile ? selectedFile.name : 'Choose CSV File'}
            <input
              type="file"
              hidden
              onChange={handleFileChange}
              accept=".csv"
            />
          </Button>
          <Button
            variant="contained"
            color="secondary"
            onClick={handleFileUpload}
            disabled={!selectedFile || uploadLoading}
            startIcon={uploadLoading ? <CircularProgress size={20} color="inherit" /> : <Send />}
          >
            {uploadLoading ? 'Uploading...' : 'Upload & Process'}
          </Button>
        </Stack>

        {uploadLoading && (
          <Box sx={{ width: '100%', mb: 2 }}>
            <LinearProgress variant="determinate" value={uploadProgress} />
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
              Processing: {uploadProgress}%
            </Typography>
          </Box>
        )}

        {uploadStatus && (
          <Alert
            severity={uploadStatus.severity}
            sx={{ mt: 2 }}
            icon={uploadStatus.severity === 'success' ? <CheckCircle /> : undefined}
          >
            <Typography variant="body2">{uploadStatus.message}</Typography>
            {uploadStatus.details?.next_steps && (
              <Typography variant="caption" sx={{ mt: 1, display: 'block' }}>
                {uploadStatus.details.next_steps}
              </Typography>
            )}
          </Alert>
        )}

        {documentReady && (
          <Chip
            icon={<CheckCircle />}
            label="Document Ready for Querying"
            color="success"
            sx={{ mt: 2 }}
          />
        )}
      </Card>

      <Divider sx={{ my: 3 }} />

      {/* Query Section */}
      <form onSubmit={handleSubmit}>
        <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2 }}>
          <AutoAwesome color="primary" />
          <Typography variant="h6">Step 2: Ask Your Question</Typography>
        </Stack>

        <TextField
          fullWidth
          multiline
          rows={4}
          variant="outlined"
          label="Enter your query"
          placeholder="Examples:
- Is member M1001 active?
- What is the deductible for member M1234?
- How many massage therapy visits has member M5678 used?
- Is acupuncture covered under the plan?"
          value={inputQuery}
          onChange={(e) => setInputQuery(e.target.value)}
          error={!!error}
          helperText={error || 'The AI will automatically route your query to the right agent'}
          sx={{ mb: 2 }}
        />

        <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
          <Button
            type="submit"
            variant="contained"
            color="primary"
            size="large"
            disabled={loading || !inputQuery.trim()}
            sx={{ borderRadius: '8px', textTransform: 'none', py: 1.5 }}
            startIcon={loading ? <CircularProgress size={24} color="inherit" /> : <Receipt />}
          >
            {loading ? 'Processing...' : 'Get Answer'}
          </Button>
          {metrics.duration && <ExecutionTimeBadge time={metrics.duration} />}
        </Stack>
      </form>

      {/* Response Display */}
      {response && (
        <Paper elevation={3} sx={{ p: 3, mt: 3, bgcolor: '#f9fafb', border: '1px solid #e0e0e0' }}>
          <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2 }}>
            <Description color="primary" />
            <Typography variant="h6">Response</Typography>
          </Stack>

          {/* Intent and Agent Info */}
          <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap">
            <Chip
              label={`Intent: ${response.intent}`}
              color="primary"
              size="small"
            />
            <Chip
              label={`Agent: ${response.agent}`}
              color="secondary"
              size="small"
            />
            <Chip
              label={`Confidence: ${(response.confidence * 100).toFixed(0)}%`}
              color="info"
              size="small"
            />
          </Stack>

          {/* Reasoning */}
          {response.reasoning && (
            <Alert severity="info" sx={{ mb: 2 }}>
              <Typography variant="body2">
                <strong>AI Reasoning:</strong> {response.reasoning}
              </Typography>
            </Alert>
          )}

          {/* Main Result */}
          <Card variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle2" gutterBottom color="primary">
              Answer:
            </Typography>
            <Box sx={{
              whiteSpace: 'pre-wrap',
              fontFamily: typeof response.result === 'object' ? 'inherit' : 'monospace'
            }}>
              {formatResultData(response.result)}
            </Box>
          </Card>

          {/* Extracted Entities */}
          {response.entities && Object.keys(response.entities).length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="caption" color="text.secondary">
                Extracted Entities:
              </Typography>
              <Stack direction="row" spacing={1} sx={{ mt: 0.5 }} flexWrap="wrap">
                {Object.entries(response.entities).map(([key, value]) => (
                  <Chip
                    key={key}
                    label={`${key}: ${value}`}
                    size="small"
                    variant="outlined"
                  />
                ))}
              </Stack>
            </Box>
          )}
        </Paper>
      )}
    </Paper>
  );

  return (
    <ThemeProvider theme={theme}>
      <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
        <Container maxWidth="lg" sx={{ py: 4 }}>
          <Box sx={{ mb: 4 }}>
            <Stack direction="row" alignItems="center" spacing={2} sx={{ mb: 1 }}>
              <MedicalInformation color="primary" sx={{ fontSize: 40 }} />
              <Typography variant="h4" component="h1">
                Member Benefit AI Assistant
              </Typography>
            </Stack>
            <Typography variant="body1" sx={{
              opacity: 0.9, fontStyle: 'italic',
              color: '#2ecc71', textShadow: '1px 1px 2px rgba(102, 174, 246, 0.3)'
            }}>
              "Handles routine tasks so you can focus on what matters most"
            </Typography>
          </Box>

          <Paper sx={{ mb: 3 }}>
            <Tabs value={activeTab} onChange={handleTabChange} variant="fullWidth">
              <Tab label="Member Benefit Inquiry" />
            </Tabs>
          </Paper>

          {activeTab === 0 && renderMemberBenefitTab()}
        </Container>
      </Box>
    </ThemeProvider>
  );
};

export default App;
