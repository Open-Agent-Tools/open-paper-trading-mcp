import { createTheme } from '@mui/material/styles';

// Define the color palette based on the style guide
const theme = createTheme({
  palette: {
    mode: 'light', // Switched to light mode
    primary: {
      main: '#1f4788', // --primary-blue
      light: '#3f67a8',
      dark: '#0f2748',
    },
    secondary: {
      main: '#1f7a4f', // --primary-green
      light: '#3f9a6f',
      dark: '#0f5a2f',
    },
    background: {
      default: '#f8f9fa', // --neutral-light
      paper: '#ffffff',   // White paper for contrast
    },
    text: {
      primary: '#212529',   // --neutral-darkest
      secondary: '#495057', // --neutral-darker
    },
    success: {
      main: '#006b3c',
      light: '#d4edda',
    },
    warning: {
      main: '#b45309',
      light: '#fff3cd',
    },
    error: {
      main: '#dc3545',
      light: '#f8d7da',
    },
    info: {
      main: '#0c5aa6',
      light: '#d1ecf1',
    },
  },
  typography: {
    fontFamily: "'Roboto', sans-serif",
    h1: { fontSize: '2.5rem', fontWeight: 300 },
    h2: { fontSize: '1.75rem', fontWeight: 400 },
    h3: { fontSize: '1.25rem', fontWeight: 500 },
    body1: { fontSize: '1rem' },
    button: { fontWeight: 500 },
  },
  components: {
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#0f2748', // --primary-blue-dark
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundColor: '#ffffff', // White paper
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundColor: '#ffffff', // White card
        },
      },
    },
  },
});

export default theme;
