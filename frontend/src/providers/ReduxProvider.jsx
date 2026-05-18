import { Provider } from 'react-redux'
import { PersistGate } from 'redux-persist/integration/react'
import { store, persistor } from '@/store'

export default function ReduxProvider({ children }) {
  return (
    <Provider store={store}>
      <PersistGate loading={<div />} persistor={persistor}>
        {children}
      </PersistGate>
    </Provider>
  )
}
