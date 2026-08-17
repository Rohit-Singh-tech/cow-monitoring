import React, { createContext, useContext, useState, useEffect } from 'react';

const ConfigContext = createContext();

export function useConfig() {
  return useContext(ConfigContext);
}

export function ConfigProvider({ children, apiBase }) {
  const [activities, setActivities] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await fetch(`${apiBase}/api/config/activities`);
        const data = await response.json();
        if (data.success && data.activities) {
          setActivities(data.activities);
        }
      } catch (error) {
        console.error('Failed to fetch activity configuration:', error);
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
