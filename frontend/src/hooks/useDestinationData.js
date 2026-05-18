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

/**
 * Lazy-loads destination lookup lists once per component lifecycle.
 *
 * Options:
 *   withConferences  — also fetch conferences (used by Destinations page)
 *   withFaxBoxes     — also fetch fax boxes   (used by Destinations page)
 *
 * Usage:
 *   const { destData, destLoading, loadDestData } = useDestinationData()
 *   const { destData, destLoading, loadDestData } = useDestinationData({ withConferences: true, withFaxBoxes: true })
 *   // call loadDestData() when the dialog opens
 */
export function useDestinationData({ withConferences = false, withFaxBoxes = false } = {}) {
  const loadedRef = useRef(false)
  const [destLoading, setDestLoading] = useState(false)
  const [destData, setDestData] = useState({
    extensions: [], voicemails: [], ivr_menus: [], ring_groups: [],
    custom_destinations: [], working_hours: [],
    ...(withConferences ? { conferences: [] } : {}),
    ...(withFaxBoxes    ? { fax_boxes: [] }   : {}),
  })

  const loadDestData = useCallback(async () => {
    if (loadedRef.current) return
    setDestLoading(true)
    try {
      const base = await Promise.all([
        extensionsApi.list({ page_size: 500, enabled: true }),
        voicemailsApi.list({ page_size: 500, voicemail_enabled: true }),
        ivrMenusApi.list({ page_size: 500, ivr_menu_enabled: true }),
        ringGroupsApi.list({ page_size: 500, ring_group_enabled: true }),
        customDestinationsApi.list({ page_size: 500, enabled: true }),
        workingHoursApi.list({ page_size: 500, working_hours_enabled: true }),
      ])
      const extras = await Promise.all([
        withConferences ? conferencesApi.list({ page_size: 500 }) : null,
        withFaxBoxes    ? faxApi.list({ page_size: 500 })         : null,
      ])
      setDestData({
        extensions:          norm(base[0]),
        voicemails:          norm(base[1]),
        ivr_menus:           norm(base[2]),
        ring_groups:         norm(base[3]),
        custom_destinations: norm(base[4]),
        working_hours:       norm(base[5]),
        ...(withConferences && extras[0] ? { conferences: norm(extras[0]) } : {}),
        ...(withFaxBoxes    && extras[1] ? { fax_boxes:   norm(extras[1]) } : {}),
      })
      loadedRef.current = true
    } finally { setDestLoading(false) }
  }, [withConferences, withFaxBoxes])

  return { destData, destLoading, loadDestData }
}
