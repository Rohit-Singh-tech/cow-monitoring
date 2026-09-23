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

export const formatDetailedDuration = (hours) => {
    if (hours === undefined || hours === null) return '0m 0s';
    const numHours = parseFloat(hours);
    if (isNaN(numHours) || numHours <= 0) return '0m 0s';

    const totalSec = Math.round(numHours * 3600);
    if (totalSec <= 0) return '0m 0s';

    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const s = totalSec % 60;

    if (h > 0) {
        return `${h}h ${m}m ${s}s`;
    }
    return `${m}m ${s}s`;
};
