import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import { tenants as tenantsApi } from '@/api'

export const fetchTenantsThunk = createAsyncThunk('tenant/fetchAll', async (_, { getState }) => {
  const { data } = await tenantsApi.list()
  const list = data.results ?? data
  const current = getState().tenant.currentTenant
  const fresh = current
    ? list.find((t) => t.tenant_uuid === current.tenant_uuid) ?? list[0] ?? null
    : list[0] ?? null
  return { list, current: fresh }
})

const tenantSlice = createSlice({
  name: 'tenant',
  initialState: {
    currentTenant: null,
    tenantList: [],
  },
  reducers: {
    setCurrentTenant: (state, action) => { state.currentTenant = action.payload },
  },
  extraReducers: (builder) => {
    builder.addCase(fetchTenantsThunk.fulfilled, (state, { payload }) => {
      state.tenantList = payload.list
      state.currentTenant = payload.current
    })
  },
})

export const { setCurrentTenant } = tenantSlice.actions
export default tenantSlice.reducer
