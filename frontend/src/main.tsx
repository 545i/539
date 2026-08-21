import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import {GameProvider} from './api/useGame';
import {GroupsProvider} from './api/useGroups';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <GameProvider>
      <GroupsProvider>
        <App />
      </GroupsProvider>
    </GameProvider>
  </StrictMode>,
);
