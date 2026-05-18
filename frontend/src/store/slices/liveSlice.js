/**
 * liveSlice — stores all real-time data pushed via WebSocket.
 * The WebSocket connection itself is managed as a side-effect in
 * src/providers/LiveProvider.jsx, which dispatches actions here.
 */
import { createSlice } from '@reduxjs/toolkit'

const liveSlice = createSlice({
  name: 'live',
  initialState: {
    wsConnected: false,
    activeCalls: [],
    registrations: [],
    extStatuses: {},          // { '1001': 'online' | 'offline' | 'ringing' | 'in_use' }
    extSnapshotReceived: false,
    systemMetrics: null,
    fsStatus: null,
    dbStatus: null,
  },
  reducers: {
    setWsConnected:    (state, { payload }) => { state.wsConnected = payload },
    setActiveCalls:    (state, { payload }) => { state.activeCalls = payload },
    setRegistrations:  (state, { payload }) => { state.registrations = payload },
    setSystemMetrics:  (state, { payload }) => { state.systemMetrics = payload },
    setFsStatus:       (state, { payload }) => { state.fsStatus = payload },
    setDbStatus:       (state, { payload }) => { state.dbStatus = payload },
    setExtSnapshot:    (state, { payload }) => {
      state.extStatuses = payload
      state.extSnapshotReceived = true
    },
    updateExtStatus:   (state, { payload: { extension, status } }) => {
      state.extStatuses[extension] = status
    },
  },
})

export const {
  setWsConnected,
  setActiveCalls,
  setRegistrations,
  setSystemMetrics,
  setFsStatus,
  setDbStatus,
  setExtSnapshot,
  updateExtStatus,
} = liveSlice.actions

export default liveSlice.reducer
