import React, { useState } from 'react';
import {
  Box,
  Button,
  TextField,
  Typography,
  Stack,
  Chip,
  Alert,
  IconButton,
  Divider,
  CircularProgress,
  Tooltip
} from '@mui/material';
import {
  ThumbUp,
  ThumbDown,
  Build,
  Send,
  Close,
  ContentCopy
} from '@mui/icons-material';

const FeedbackControl = ({ conversationId, conversationType, apiEndpoint = '/api/feedback' }) => {
  const [feedbackRating, setFeedbackRating] = useState(null);
  const [feedbackComment, setFeedbackComment] = useState('');
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [apiResponse, setApiResponse] = useState(null);
  const [copyTooltip, setCopyTooltip] = useState('Copy to clipboard');

  const handleRatingClick = (rating) => {
    setFeedbackRating(rating);
    setError(null);
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(conversationId);
    setCopyTooltip('Copied!');
    setTimeout(() => setCopyTooltip('Copy to clipboard'), 2000);
  };

  const submitFeedbackToAPI = async (feedbackData) => {
    try {
      const response = await fetch(process.env.REACT_APP_FEEDBACK_NODE_API_URL || 'http://127.0.0.1:5000/api/feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          conversation_id: feedbackData.conversation_id,
          conversation_type: feedbackData.conversation_type,
          feedback_rate: feedbackData.feedback_rate,
          feedback_comment: feedbackData.feedback_comment
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || 'Failed to submit feedback');
      }

      return data;
    } catch (err) {
      console.error('Feedback API Error:', err);
      throw err;
    }
  };

  const handleSubmit = async () => {
    if (!feedbackRating) {
      setError('Please select a rating before submitting');
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setApiResponse(null);

    try {
      const response = await submitFeedbackToAPI({
        conversation_id: conversationId,
        conversation_type: conversationType,
        feedback_rate: feedbackRating,
        feedback_comment: feedbackComment
      });

      setApiResponse(response);
      setIsSubmitted(true);
    } catch (err) {
      setError(err.message || 'Failed to submit feedback. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetFeedback = () => {
    setFeedbackRating(null);
    setFeedbackComment('');
    setIsSubmitted(false);
    setError(null);
    setApiResponse(null);
  };

  if (isSubmitted && apiResponse) {
    return (
      <Box sx={{ mt: 3, p: 2, border: '1px solid #e0e0e0', borderRadius: 1 }}>
        <Alert
          severity="success"
          action={
            <IconButton size="small" onClick={resetFeedback}>
              <Close fontSize="small" />
            </IconButton>
          }
        >
          <Box>
            <Typography>{apiResponse.message}</Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              Conversation ID: {apiResponse.conversation_id}
            </Typography>
          </Box>
        </Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ mt: 3, p: 3, border: '1px solid #e0e0e0', borderRadius: 1 }}>
      <Box sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        mb: 2,
        p: 1,
        backgroundColor: '#f5f5f5',
        borderRadius: 1
      }}>
        <Typography variant="subtitle2">
          Conversation ID: {conversationId}
        </Typography>
        <Tooltip title={copyTooltip} placement="top">
          <IconButton size="small" onClick={copyToClipboard}>
            <ContentCopy fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      <Typography variant="h6" gutterBottom>
        Was this response helpful?
      </Typography>

      <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
        <Chip
          icon={<ThumbUp />}
          label="Correct"
          clickable
          color={feedbackRating === 'Correct' ? 'success' : 'default'}
          onClick={() => handleRatingClick('Correct')}
          variant={feedbackRating === 'Correct' ? 'filled' : 'outlined'}
        />
        <Chip
          icon={<ThumbDown />}
          label="Incorrect"
          clickable
          color={feedbackRating === 'Incorrect' ? 'error' : 'default'}
          onClick={() => handleRatingClick('Incorrect')}
          variant={feedbackRating === 'Incorrect' ? 'filled' : 'outlined'}
        />
        <Chip
          icon={<Build />}
          label="Needs Improvement"
          clickable
          color={feedbackRating === 'Need Improvements' ? 'warning' : 'default'}
          onClick={() => handleRatingClick('Need Improvements')}
          variant={feedbackRating === 'Need Improvements' ? 'filled' : 'outlined'}
        />
      </Stack>

      {feedbackRating && (
        <>
          <Divider sx={{ my: 2 }} />
          <TextField
            fullWidth
            multiline
            rows={3}
            variant="outlined"
            label="Additional feedback (optional)"
            value={feedbackComment}
            onChange={(e) => setFeedbackComment(e.target.value)}
            placeholder="Please share more details about your experience..."
            sx={{ mb: 2 }}
          />
        </>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Button
        variant="contained"
        color="primary"
        startIcon={isSubmitting ? <CircularProgress size={20} color="inherit" /> : <Send />}
        onClick={handleSubmit}
        disabled={!feedbackRating || isSubmitting}
      >
        {isSubmitting ? 'Submitting...' : 'Submit Feedback'}
      </Button>
    </Box>
  );
};

export default FeedbackControl;
