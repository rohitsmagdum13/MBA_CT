import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Tabs,
  Tab,
  Divider,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Radio,
  Link,
  Alert,
  Button,
  Chip,
  Skeleton,
  Switch,
  FormControlLabel,
  styled,
  Paper
} from '@mui/material';
import {
  Description,
  RocketLaunch,
  Visibility,
  FolderOff,
  CheckCircleOutline,
  PictureAsPdf,
  Refresh,
  FilterList
} from '@mui/icons-material';

// Styled Components
const StyledPaper = styled(Paper)(({ theme }) => ({
  borderRadius: theme.shape.borderRadius * 2,
  padding: theme.spacing(3),
  marginBottom: theme.spacing(3),
  boxShadow: theme.shadows[3],
  backgroundColor: theme.palette.background.paper,
}));

const DocumentListContainer = styled(List)(({ theme }) => ({
  maxHeight: '400px',
  overflow: 'auto',
  '&::-webkit-scrollbar': {
    width: '6px'
  },
  '&::-webkit-scrollbar-thumb': {
    backgroundColor: theme.palette.divider,
    borderRadius: theme.shape.borderRadius
  }
}));

const DocumentViewer = ({
  documents,
  loading,
  selectedDocument,
  setSelectedDocument,
  planNumber // Pass the current plan number as prop
}) => {
  const [activeDocumentTab, setActiveDocumentTab] = useState('PS Docs');
  const [sortedDocumentKeys, setSortedDocumentKeys] = useState([]);
  const [filterByPlanNumber, setFilterByPlanNumber] = useState(false);

  // Sort document tabs with Current first and alphabetize the rest
  useEffect(() => {
    if (documents) {
      const keys = Object.keys(documents);
      setSortedDocumentKeys([
        ...keys.filter(k => k === 'PS Docs'),
        ...keys.filter(k => k !== 'PS Docs').sort()
      ]);

      if (keys.includes('PS Docs')) {
        setActiveDocumentTab('PS Docs');
      } else if (keys.length > 0) {
        setActiveDocumentTab(keys[0]);
      }
    }
  }, [documents]);

  // Filter documents based on plan number
  const filterDocuments = (docs) => {
    if (!filterByPlanNumber || !planNumber) return docs;

    return docs.filter(doc =>
      doc.file_name && doc.file_name.includes(planNumber)
    );
  };

  const handleRefresh = () => {
    // Add your refresh logic here
    console.log('Refreshing documents...');
  };

  const handleFilterToggle = () => {
    setFilterByPlanNumber(!filterByPlanNumber);
  };

  return (
    <StyledPaper>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Description color="primary" sx={{ mr: 1.5, fontSize: '1.5rem' }} />
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Available Documents
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Button
            startIcon={<Refresh />}
            onClick={handleRefresh}
            size="small"
            sx={{ textTransform: 'none', mr: 2 }}
          >
            Refresh
          </Button>
          <FormControlLabel
            control={
              <Switch
                checked={filterByPlanNumber}
                onChange={handleFilterToggle}
                color="primary"
                size="small"
              />
            }
            label={
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <FilterList fontSize="small" sx={{ mr: 0.5 }} />
                Filter by Plan
              </Box>
            }
            sx={{ m: 0 }}
          />
        </Box>
      </Box>

      {loading ? (
        <Box sx={{ p: 2 }}>
          <Skeleton variant="rectangular" height={40} sx={{ mb: 1 }} />
          <Skeleton variant="rectangular" height={56} sx={{ mb: 1 }} />
          <Skeleton variant="rectangular" height={56} sx={{ mb: 1 }} />
          <Skeleton variant="rectangular" height={56} />
        </Box>
      ) : documents ? (
        <>
          <Tabs
            value={activeDocumentTab}
            onChange={(e, newValue) => setActiveDocumentTab(newValue)}
            variant="scrollable"
            scrollButtons="auto"
            sx={{
              mb: 2,
              '& .MuiTabs-indicator': {
                height: 3,
                backgroundColor: 'primary.main'
              }
            }}
          >
            {sortedDocumentKeys.map((folder) => (
              <Tab
                key={folder}
                label={
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    {folder === 'PS Docs' ? (
                      <RocketLaunch fontSize="small" sx={{ mr: 1, color: 'primary.main' }} />
                    ) : (
                      <Description fontSize="small" sx={{ mr: 1, color: 'text.secondary' }} />
                    )}
                    {folder}
                    <Chip
                      label={filterByPlanNumber ?
                        filterDocuments(documents[folder]).length :
                        documents[folder].length}
                      size="small"
                      sx={{
                        ml: 1,
                        fontSize: '0.675rem',
                        backgroundColor: folder === activeDocumentTab ? 'primary.light' : 'action.selected'
                      }}
                    />
                  </Box>
                }
                value={folder}
                sx={{
                  minWidth: 'unset',
                  px: 2,
                  fontSize: '0.875rem',
                  fontWeight: activeDocumentTab === folder ? 600 : 400,
                  color: activeDocumentTab === folder ? 'primary.main' : 'text.secondary'
                }}
              />
            ))}
          </Tabs>

          <Divider sx={{ mb: 3 }} />

          {filterByPlanNumber && planNumber && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Showing documents containing: <strong>{planNumber}</strong>
            </Alert>
          )}

          {filterDocuments(documents[activeDocumentTab])?.length > 0 ? (
            <DocumentListContainer>
              {filterDocuments(documents[activeDocumentTab]).map((doc) => (
                <ListItem
                  key={doc.file_id}
                  sx={{
                    px: 0,
                    py: 1,
                    '&:hover': {
                      backgroundColor: 'action.hover'
                    }
                  }}
                >
                  <ListItemIcon sx={{ minWidth: '48px' }}>
                    <Radio
                      edge="start"
                      checked={selectedDocument?.file_id === doc.file_id}
                      onChange={() => setSelectedDocument({
                        ...doc,
                        is_selected: true
                      })}
                      color="primary"
                    />
                  </ListItemIcon>
                  <ListItemIcon sx={{ mr: 1, minWidth: '32px' }}>
                    {doc.file_name?.endsWith('.pdf') ? (
                      <PictureAsPdf color="error" />
                    ) : (
                      <Description color="action" />
                    )}
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Typography variant="body1" sx={{ fontWeight: 500 }}>
                        {doc.file_name}
                        {filterByPlanNumber && doc.file_name.includes(planNumber) && (
                          <Chip
                            label="Plan Match"
                            size="small"
                            color="success"
                            sx={{ ml: 1, fontSize: '0.625rem', height: '20px' }}
                          />
                        )}
                      </Typography>
                    }
                    secondary={
                      <Box sx={{ display: 'flex', alignItems: 'center', mt: 0.5 }}>
                        <Link
                          href={doc.preview_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          sx={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            color: 'primary.main',
                            textDecoration: 'none',
                            '&:hover': {
                              textDecoration: 'underline'
                            }
                          }}
                        >
                          <Visibility fontSize="small" sx={{ mr: 0.5 }} />
                          Preview
                        </Link>
                        {doc.last_modified && (
                          <Typography variant="caption" sx={{ ml: 2, color: 'text.secondary' }}>
                            Modified: {new Date(doc.last_modified).toLocaleDateString()}
                          </Typography>
                        )}
                      </Box>
                    }
                    sx={{ my: 0 }}
                  />
                </ListItem>
              ))}
            </DocumentListContainer>
          ) : (
            <Box sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              py: 4,
              color: 'text.disabled'
            }}>
              <FolderOff fontSize="large" />
              <Typography variant="body1" sx={{ mt: 1 }}>
                {filterByPlanNumber && planNumber ?
                  `No documents found containing "${planNumber}"` :
                  'No documents available in this category'}
              </Typography>
            </Box>
          )}
        </>
      ) : (
        <Box sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          py: 4,
          color: 'text.disabled'
        }}>
          <Typography variant="body1">
            No documents loaded
          </Typography>
        </Box>
      )}

      {selectedDocument && (
        <Alert
          severity="info"
          icon={<CheckCircleOutline />}
          sx={{
            mt: 2,
            border: '1px solid',
            borderColor: 'primary.light',
            backgroundColor: 'primary.lighter',
            '& .MuiAlert-message': {
              width: '100%'
            }
          }}
        >
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography>
              Selected: <strong>{selectedDocument.file_name}</strong>
            </Typography>
            <Button
              size="small"
              onClick={() => setSelectedDocument(null)}
              sx={{ ml: 2 }}
            >
              Clear Selection
            </Button>
          </Box>
        </Alert>
      )}
    </StyledPaper>
  );
};

export default DocumentViewer;
