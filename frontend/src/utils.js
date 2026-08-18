export const formatHours = (hours) => {
    if (hours === undefined || hours === null) return '0m';
    const numHours = parseFloat(hours);
    if (isNaN(numHours)) return '0m';
    if (numHours === 0) return '0m';
    
    const h = Math.floor(numHours);
    const m = Math.round((numHours - h) * 60);
    
    if (h === 0) return `${m}m`;
    if (m === 0) return `${h}h`;
    return `${h}h ${m}m`;
};
