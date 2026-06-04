import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import { auth as authApi, broadcastLogout } from '@/api'
import axios from 'axios'

export const loginThunk = createAsyncThunk('auth/login', async ({ username, password }, { rejectWithValue }) => {
  try {
    const { data } = await authApi.login({ username, password })
    // Pass token explicitly in config — localStorage not populated yet at this point
    const me = await axios.get('/api/v1/auth/me/', {
      headers: { Authorization: `Bearer ${data.access}` },
    })
    return { accessToken: data.access, refreshToken: data.refresh, user: me.data }
  } catch (err) {
    return rejectWithValue(err?.response?.data ?? { detail: 'Login failed' })
  }
})

// Re-fetch the current user's record so permission/role/tenant changes made by
// an admin take effect without a re-login. Silent: on failure (other than auth,
// which the interceptor handles) it leaves the existing user in place.
export const refreshUserThunk = createAsyncThunk('auth/refreshUser', async (_, { getState, rejectWithValue }) => {
  const { isAuthenticated, accessToken } = getState().auth
  if (!isAuthenticated || !accessToken) return rejectWithValue('not-authenticated')
  try {
    const { data } = await authApi.me()
    return data
  } catch (err) {
    return rejectWithValue(err?.response?.data ?? { detail: 'refresh failed' })
  }
})

export const logoutThunk = createAsyncThunk('auth/logout', async (_, { getState }) => {
  const { refreshToken } = getState().auth
  try { if (refreshToken) await authApi.logout(refreshToken) } catch {}
  try { broadcastLogout() } catch {}
})

const authSlice = createSlice({
  name: 'auth',
  initialState: {
    user: null,
    accessToken: null,
    refreshToken: null,
    isAuthenticated: false,
    loading: false,
    error: null,
  },
  reducers: {
    setUser: (state, action) => { state.user = action.payload },
    setAccessToken: (state, action) => { state.accessToken = action.payload },
    setTokens: (state, action) => {
      const { access, refresh } = action.payload || {}
      if (access) state.accessToken = access
      if (refresh) state.refreshToken = refresh
    },
    clearAuth: (state) => {
      state.user = null
      state.accessToken = null
      state.refreshToken = null
      state.isAuthenticated = false
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(loginThunk.pending, (state) => { state.loading = true; state.error = null })
      .addCase(loginThunk.fulfilled, (state, { payload }) => {
        state.loading = false
        state.accessToken = payload.accessToken
        state.refreshToken = payload.refreshToken
        state.user = payload.user
        state.isAuthenticated = true
      })
      .addCase(loginThunk.rejected, (state, { payload }) => {
        state.loading = false
        state.error = payload?.detail ?? 'Login failed'
      })
      .addCase(refreshUserThunk.fulfilled, (state, { payload }) => {
        // Only update while still authenticated (guards against a logout race).
        if (state.isAuthenticated && payload) state.user = payload
      })
      .addCase(logoutThunk.fulfilled, (state) => {
        state.user = null
        state.accessToken = null
        state.refreshToken = null
        state.isAuthenticated = false
      })
  },
})

export const { setUser, setAccessToken, setTokens, clearAuth } = authSlice.actions
export default authSlice.reducer
