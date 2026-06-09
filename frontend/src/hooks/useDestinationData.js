import { useState, useRef, useCallback } from 'react'
import {
  extensions as extensionsApi,
  voicemails as voicemailsApi,
  ivrMenus as ivrMenusApi,
  ringGroups as ringGroupsApi,
  customDestinations as customDestinationsApi,
  workingHours as workingHoursApi,
  conferences as conferencesApi,
  fax as faxApi,
} from '@/api'

const norm = (res) => Array.isArray(res.data) ? res.data : res.data.results || []

async function fetchPage(apiFn, extraParams = {}, search = '') {
  const params = { page_size: 100, ...extraParams }
  if (search) params.search = search
  return norm(await apiFn(params))
}

/**
 * Lazy-loads destination lookup lists once per component lifecycle.
 * Exposes a `searchDestData(query)` function that re-fetches all types
 * with a search filter so the picker always covers every record.
 *
 * Options:
 *   withConferences  — also fetch conferences (used by Destinations page)
 *   withFaxBoxes     — also fetch fax boxes   (used by Destinations page)
 */
export function useDestinationData({ withConferences = false, withFaxBoxes = false } = {}) {
  const loadedRef    = useRef(false)
  const searchingRef = useRef(false)
  const [destLoading,       setDestLoading]       = useState(false)
  const [destSearchLoading, setDestSearchLoading] = useState(false)
  const [destData, setDestData] = useState({
    extensions: [], voicemails: [], ivr_menus: [], ring_groups: [],
    custom_destinations: [], working_hours: [],
    ...(withConferences ? { conferences: [] } : {}),
    ...(withFaxBoxes    ? { fax_boxes: [] }   : {}),
  })

  const _fetch = useCallback(async (search = '') => {
    const [extensions, voicemails, ivr_menus, ring_groups, custom_destinations, working_hours] =
      await Promise.all([
        fetchPage(extensionsApi.list,         { enabled: true },              search),
        fetchPage(voicemailsApi.list,         { voicemail_enabled: true },    search),
        fetchPage(ivrMenusApi.list,           { ivr_menu_enabled: true },     search),
        fetchPage(ringGroupsApi.list,         { ring_group_enabled: true },   search),
        fetchPage(customDestinationsApi.list, { enabled: true },              search),
        fetchPage(workingHoursApi.list,       { working_hours_enabled: true },search),
      ])

    const conferences = withConferences ? await fetchPage(conferencesApi.list, {}, search) : []
    const fax_boxes   = withFaxBoxes    ? await fetchPage(faxApi.list,         {}, search) : []

    return {
      extensions, voicemails, ivr_menus, ring_groups, custom_destinations, working_hours,
      ...(withConferences ? { conferences } : {}),
      ...(withFaxBoxes    ? { fax_boxes }   : {}),
    }
  }, [withConferences, withFaxBoxes])

  // Initial load — called when the dialog opens.
  const loadDestData = useCallback(async () => {
    if (loadedRef.current) return
    setDestLoading(true)
    try {
      setDestData(await _fetch(''))
      loadedRef.current = true
    } finally { setDestLoading(false) }
  }, [_fetch])

  // Search — called by the picker when the user types.
  // If query is empty, restores the initial unfiltered load.
  const searchDestData = useCallback(async (query) => {
    searchingRef.current = true
    setDestSearchLoading(true)
    try {
      setDestData(await _fetch(query.trim()))
    } finally {
      setDestSearchLoading(false)
      searchingRef.current = false
    }
  }, [_fetch])

  // Re-fetch only the fax box list (e.g. after creating/editing a box inline).
  const reloadFaxBoxes = useCallback(async () => {
    if (!withFaxBoxes) return
    const boxes = await fetchPage(faxApi.list, {})
    setDestData(prev => ({ ...prev, fax_boxes: boxes }))
  }, [withFaxBoxes])

  return { destData, destLoading, destSearchLoading, loadDestData, searchDestData, reloadFaxBoxes }
}
