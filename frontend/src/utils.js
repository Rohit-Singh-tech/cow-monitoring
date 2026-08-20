export const formatHours = (hours) => {
    if (hours === undefined || hours === null) return '0m';
    const numHours = parseFloat(hours);
    if (isNaN(numHours)) return '0m';
    if (numHours === 0) return '0m';
    
    const h = Math.floor(numHours);
    const m = Math.floor((numHours - h) * 60);
    const s = Math.round((numHours - h - m / 60) * 3600);
    
    if (h === 0 && m === 0) {
        if (s === 0) return '0m';
        return `${s}s`;
    }
    
    if (h === 0) return `${m}m`;
    if (m === 0) return `${h}h`;
    return `${h}h ${m}m`;
};
