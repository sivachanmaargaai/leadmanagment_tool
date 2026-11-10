export const divisions = ["MMC", "nemilink", "ClearCode Labs", "ENGEN", "Visotonics", "Overview"];

export function divisionLabel(value) {
    return value === "nemilink" ? "Nemilink" : value;
}

export const statuses = [
    "New",
    "In Progress",
    "Follow-up",
    "Won",
    "Lost",
];

export function initials(name) {
    return name
        .trim()
        .split(/\s+/)
        .slice(0, 2)
        .map((word) => word[0])
        .join("")
        .toUpperCase();
}

export function statusClass(value) {
    return value.toLowerCase().replaceAll(" ", "-");
}

export const initialLeads = [
    {
        id: "LD-1001",
        customer: "Arun Industries",
        contact: "Arun Kumar",
        division: "nemilink",
        description: "Industrial IoT monitoring system",
        status: "In Progress",
        priority: "High",
    },
    {
        id: "LD-1002",
        customer: "Greenfield Automation",
        contact: "Priya R",
        division: "MMC",
        description: "Custom embedded controller",
        status: "New",
        priority: "High",
    },
    {
        id: "LD-1003",
        customer: "Vertex Engineering",
        contact: "Karthik S",
        division: "ClearCode Labs",
        description: "Device management dashboard",
        status: "Follow-up",
        priority: "Medium",
    },
    {
        id: "LD-1004",
        customer: "Nova Systems",
        contact: "Deepa M",
        division: "MMC",
        description: "Firmware development",
        status: "Won",
        priority: "Medium",
    },
    {
        id: "LD-1005",
        customer: "Precision Controls",
        contact: "Suresh V",
        division: "nemilink",
        description: "Wireless sensor integration",
        status: "New",
        priority: "Low",
    },
];
