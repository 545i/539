import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import {GameProvider} from './api/useGame';
import {GroupsProvider} from './api/useGroups';
import {EditionsProvider} from './api/useEditions';
import {WeekFocusProvider} from './components/WeekNav';
import {LedgerProvider} from './api/useLedger';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <GameProvider>
      <GroupsProvider>
        <EditionsProvider>
          <LedgerProvider>
            <WeekFocusProvider>
              <App />
            </WeekFocusProvider>
          </LedgerProvider>
        </EditionsProvider>
      </GroupsProvider>
    </GameProvider>
  </StrictMode>,
);
