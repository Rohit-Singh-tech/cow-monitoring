import React, { createContext, useContext, useState, useEffect } from 'react';

const ConfigContext = createContext();

export function useConfig() {
  return useContext(ConfigContext);
}

const DEFAULT_ACTIVITIES = {
  RES: { code: 'RES', name: 'Standing Rest', color: '#64748B', icon: 'fa-pause' },
  RUS: { code: 'RUS', name: 'Ruminating', color: '#06B6D4', icon: 'fa-arrows-spin' },
  MOV: { code: 'MOV', name: 'Moving / Active', color: '#F59E0B', icon: 'fa-person-walking' },
  FEP: { code: 'FEP', name: 'Feeding in Pot', color: '#10B981', icon: 'fa-bowl-food' },
  FED: { code: 'FED', name: 'Feeding', color: '#10B981', icon: 'fa-bowl-food' },
  GRZ: { code: 'GRZ', name: 'Grazing Field', color: '#10B981', icon: 'fa-wheat-awn' },
  DRN: { code: 'DRN', name: 'Drinking Water', color: '#0EA5E9', icon: 'fa-glass-water' },
  LCK: { code: 'LCK', name: 'Licking', color: '#EC4899', icon: 'fa-hand-sparkles' },
  REL: { code: 'REL', name: 'Lying Rest', color: '#8B5CF6', icon: 'fa-bed' },
  URI: { code: 'URI', name: 'Urinating', color: '#FDE047', icon: 'fa-droplet' },
  DEF: { code: 'DEF', name: 'Defecating', color: '#FB923C', icon: 'fa-circle-dot' },
  ATT: { code: 'ATT', name: 'Attacking', color: '#EF4444', icon: 'fa-triangle-exclamation' },
  OTH: { code: 'OTH', name: 'Other', color: '#94A3B8', icon: 'fa-question' }
};

export function ConfigProvider({ children, apiBase }) {
  const [activities, setActivities] = useState(DEFAULT_ACTIVITIES);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await fetch(`${apiBase}/api/config/activities`);
        const data = await response.json();
        if (data.success && data.activities && Object.keys(data.activities).length > 0) {
          setActivities(data.activities);
        } else {
          setActivities(DEFAULT_ACTIVITIES);
        }
      } catch (error) {
        console.error('Failed to fetch activity configuration, using fallback:', error);
        setActivities(DEFAULT_ACTIVITIES);
      } finally {
        setLoading(false);
      }
    };

    fetchConfig();
  }, [apiBase]);

  return (
    <ConfigContext.Provider value={{ activities, loading }}>
      {children}
    </ConfigContext.Provider>
  );
}
