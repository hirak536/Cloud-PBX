import { configureStore, combineReducers } from '@reduxjs/toolkit'
import { persistStore, persistReducer, FLUSH, REHYDRATE, PAUSE, PERSIST, PURGE, REGISTER } from 'redux-persist'
import authReducer   from './slices/authSlice'
import themeReducer  from './slices/themeSlice'
import tenantReducer from './slices/tenantSlice'
import liveReducer   from './slices/liveSlice'

const storage = {
  getItem:    (key) => Promise.resolve(localStorage.getItem(key)),
  setItem:    (key, value) => Promise.resolve(localStorage.setItem(key, value)),
  removeItem: (key) => Promise.resolve(localStorage.removeItem(key)),
}

const rootReducer = combineReducers({
  auth:   persistReducer({ key: 'auth',   storage, whitelist: ['user', 'accessToken', 'refreshToken', 'isAuthenticated'] }, authReducer),
  theme:  persistReducer({ key: 'theme',  storage }, themeReducer),
  tenant: persistReducer({ key: 'tenant', storage, whitelist: ['currentTenant', 'tenantList'] }, tenantReducer),
  live:   liveReducer,
})

export const store = configureStore({
  reducer: rootReducer,
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        ignoredActions: [FLUSH, REHYDRATE, PAUSE, PERSIST, PURGE, REGISTER],
      },
    }),
})

export const persistor = persistStore(store)

export const selectAuth   = (s) => s.auth
export const selectTheme  = (s) => s.theme.theme
export const selectTenant = (s) => s.tenant
export const selectLive   = (s) => s.live
