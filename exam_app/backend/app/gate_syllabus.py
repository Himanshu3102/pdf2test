# GATE Syllabus Topics (branch -> subject -> topics)
# Source: Official GATE syllabus (publicly available)
GATE_SYLLABUS = {
    "CS": {
        "name": "Computer Science and Information Technology",
        "subjects": {
            "Engineering Mathematics": [
                "Discrete Mathematics", "Linear Algebra", "Calculus", "Differential Equations",
                "Complex Variables", "Probability and Statistics", "Numerical Methods",
                "Graph Theory", "Combinatorics", "Set Theory and Relations"
            ],
            "Digital Logic": [
                "Boolean Algebra", "Combinational Circuits", "Sequential Circuits",
                "Minimization", "Number Representations and Computer Arithmetic",
                "Fixed and Floating Point", "Memory and I/O Interface"
            ],
            "Computer Organization and Architecture": [
                "Machine Instructions", "ALU and Data-path", "Control Unit",
                "Instruction Pipelining", "Pipeline Hazards", "Memory Hierarchy",
                "Cache Memory", "Main Memory", "Secondary Storage",
                "I/O Interface", "Interrupt and DMA"
            ],
            "Programming and Data Structures": [
                "Programming in C", "Recursion", "Arrays", "Stacks", "Queues",
                "Linked Lists", "Trees", "Binary Search Trees", "Binary Heaps",
                "Graphs", "Hashing"
            ],
            "Algorithms": [
                "Searching", "Sorting", "Hashing", "Asymptotic Analysis",
                "Divide and Conquer", "Greedy", "Dynamic Programming",
                "Graph Algorithms", "Minimum Spanning Trees", "Shortest Paths",
                "NP-Completeness", "Approximation Algorithms"
            ],
            "Theory of Computation": [
                "Regular Expressions", "Finite Automata", "Context-Free Grammars",
                "Pushdown Automata", "Regular and CFL", "Pumping Lemma",
                "Turing Machines", "Decidability", "Undecidability",
                "Recursively Enumerable Languages"
            ],
            "Compiler Design": [
                "Lexical Analysis", "Parsing", "LL and LR Parsing",
                "Syntax-Directed Translation", "Intermediate Code Generation",
                "Code Optimization", "Runtime Environments", "Register Allocation"
            ],
            "Operating System": [
                "Processes and Threads", "CPU Scheduling", "Process Synchronization",
                "Deadlock", "Memory Management", "Virtual Memory", "Paging",
                "Segmentation", "File Systems", "I/O Systems", "Protection and Security"
            ],
            "Databases": [
                "ER Model", "Relational Model", "Relational Algebra", "SQL",
                "Integrity Constraints", "Normal Forms", "Functional Dependencies",
                "File Organization", "Indexing", "B and B+ Trees",
                "Transactions", "Concurrency Control", "Recovery"
            ],
            "Computer Networks": [
                "OSI and TCP/IP Models", "LAN Technologies", "Switching",
                "IP Addressing", "IPv4 and IPv6", "Routing Protocols",
                "TCP and UDP", "Congestion Control", "HTTP", "DNS",
                "Email and FTP", "Network Security Basics"
            ],
        },
    },
    "EC": {
        "name": "Electronics and Communication Engineering",
        "subjects": {
            "Engineering Mathematics": [
                "Linear Algebra", "Calculus", "Differential Equations",
                "Complex Variables", "Probability and Statistics", "Numerical Methods"
            ],
            "Networks, Signals and Systems": [
                "Network Solution Methods", "Laplace Transform", "Fourier Series",
                "Z-Transform", "LTI Systems", "Sampling Theorem", "Convolution",
                "Impulse Response", "Frequency Response"
            ],
            "Electronic Devices": [
                "Energy Bands", "Carrier Transport", "PN Junction", "BJT",
                "MOSFET", "LED", "Photodetector", "Solar Cells", "Oscillators"
            ],
            "Analog Circuits": [
                "Small Signal Models", "BJT and MOSFET Amplifiers",
                "Operational Amplifiers", "Feedback", "Oscillators",
                "Active Filters", "Power Amplifiers"
            ],
            "Digital Circuits": [
                "Number Systems", "Boolean Algebra", "Combinational Circuits",
                "Sequential Circuits", "ADC and DAC", "Semiconductor Memories",
                "Microprocessor 8085/8086"
            ],
            "Control Systems": [
                "Mathematical Modeling", "Transfer Function", "Block Diagrams",
                "Transient and Steady State", "Bode Plot", "Nyquist Plot",
                "Root Locus", "Routh-Hurwitz", "State Space Model",
                "Compensators", "PID Controllers"
            ],
            "Communications": [
                "Random Signals and Noise", "Analog Communications",
                "AM, FM, PM", "Superheterodyne Receivers",
                "Digital Communications", "PCM, DPCM, DM",
                "ASK, PSK, FSK, QAM", "Information Theory", "Channel Capacity",
                "Error Control Coding", "Optical Communication"
            ],
            "Electromagnetics": [
                "Electrostatics", "Magnetostatics", "Maxwell's Equations",
                "Wave Equation", "Transmission Lines", "Waveguides",
                "Antennas", "Radiation"
            ],
        },
    },
    "EE": {
        "name": "Electrical Engineering",
        "subjects": {
            "Engineering Mathematics": [
                "Linear Algebra", "Calculus", "Differential Equations",
                "Complex Variables", "Probability and Statistics", "Numerical Methods"
            ],
            "Electric Circuits": [
                "Network Elements", "KCL and KVL", "Network Theorems",
                "Transient Analysis", "Sinusoidal Steady State",
                "Resonance", "Two-Port Networks", "Three Phase Circuits"
            ],
            "Electromagnetic Fields": [
                "Coulomb's Law", "Electric Field Intensity", "Gauss's Law",
                "Magnetic Field", "Ampere's Law", "Faraday's Law",
                "Maxwell's Equations", "Boundary Conditions"
            ],
            "Signals and Systems": [
                "Linear Time-Invariant Systems", "Convolution", "Fourier Series",
                "Laplace Transform", "Z-Transform", "Sampling", "Discrete Systems"
            ],
            "Electrical Machines": [
                "DC Machines", "Transformers", "Induction Machines",
                "Synchronous Machines", "Fractional KW Motors", "Single Phase Induction Motors"
            ],
            "Power Systems": [
                "Power Generation", "Transmission Line Parameters",
                "Corona and Radio Interference", "Insulators", "Distribution Systems",
                "Load Flow", "Fault Analysis", "Stability", "Power System Protection",
                "Circuit Breakers", "Relays"
            ],
            "Control Systems": [
                "Mathematical Modeling", "Transfer Function", "Block Diagrams",
                "Transient and Steady State", "Frequency Response", "Routh-Hurwitz",
                "Root Locus", "Nyquist", "State Space", "Compensators"
            ],
            "Electrical and Electronic Measurements": [
                "Bridges and Potentiometers", "PMMC, Moving Iron, Dynamometer",
                "Instrument Transformers", "Digital Voltmeters", "Oscilloscopes",
                "Transducers", "Data Acquisition"
            ],
            "Analog and Digital Electronics": [
                "Diodes", "BJT and MOSFET", "Operational Amplifiers",
                "Combinational and Sequential Circuits", "Microprocessor 8085",
                "ADC and DAC", "Timers"
            ],
            "Power Electronics": [
                "Power Diodes", "Thyristors", "Power Transistors", "IGBT",
                "AC to DC Converters", "DC to DC Converters", "DC to AC Converters",
                "AC to AC Converters", "PWM Techniques"
            ],
        },
    },
    "ME": {
        "name": "Mechanical Engineering",
        "subjects": {
            "Engineering Mathematics": [
                "Linear Algebra", "Calculus", "Differential Equations",
                "Complex Variables", "Probability and Statistics", "Numerical Methods"
            ],
            "Applied Mechanics and Design": [
                "Engineering Mechanics", "Strength of Materials", "Theory of Machines",
                "Vibrations", "Machine Design", "Bearings", "Gears", "Springs"
            ],
            "Fluid Mechanics and Thermal Sciences": [
                "Fluid Properties", "Fluid Statics", "Bernoulli Equation",
                "Pipe Flow", "Boundary Layer", "Turbomachinery",
                "Thermodynamics", "Heat Transfer", "Refrigeration and Air Conditioning"
            ],
            "Manufacturing and Industrial Engineering": [
                "Engineering Materials", "Metal Casting", "Forming", "Joining",
                "Machining", "Metrology and Inspection", "CNC", "Additive Manufacturing",
                "Production Planning", "Inventory Control", "Operations Research",
                "Quality Management", "Work Study"
            ],
        },
    },
    "CE": {
        "name": "Civil Engineering",
        "subjects": {
            "Engineering Mathematics": [
                "Linear Algebra", "Calculus", "Differential Equations",
                "Complex Variables", "Probability and Statistics", "Numerical Methods"
            ],
            "Structural Engineering": [
                "Mechanics", "Structural Analysis", "Concrete Structures",
                "Steel Structures", "Foundation Engineering"
            ],
            "Geotechnical Engineering": [
                "Soil Mechanics", "Foundation Engineering", "Earth Pressure",
                "Slope Stability", "Settlement Analysis"
            ],
            "Water Resources Engineering": [
                "Fluid Mechanics", "Hydraulics", "Hydrology",
                "Irrigation", "Water Supply", "Wastewater"
            ],
            "Environmental Engineering": [
                "Water Quality", "Air Pollution", "Solid Waste Management",
                "Noise Pollution", "Environmental Impact Assessment"
            ],
            "Transportation Engineering": [
                "Highway Geometry", "Traffic Engineering", "Pavement Design",
                "Railway Engineering", "Airport Engineering"
            ],
            "Geomatics Engineering": [
                "Surveying", "GPS", "Remote Sensing", "GIS"
            ],
        },
    },
}

# GATE branches list
GATE_BRANCHES = {
    "AE": "Aerospace Engineering",
    "AG": "Agricultural Engineering",
    "AR": "Architecture and Planning",
    "BM": "Biomedical Engineering",
    "BT": "Biotechnology",
    "CE": "Civil Engineering",
    "CH": "Chemical Engineering",
    "CS": "Computer Science and Information Technology",
    "CY": "Chemistry",
    "DA": "Data Science and Artificial Intelligence",
    "EC": "Electronics and Communication Engineering",
    "EE": "Electrical Engineering",
    "ES": "Environmental Science and Engineering",
    "EY": "Ecology and Evolution",
    "GE": "Geomatics Engineering",
    "GG": "Geology and Geophysics",
    "IN": "Instrumentation Engineering",
    "MA": "Mathematics",
    "ME": "Mechanical Engineering",
    "MN": "Mining Engineering",
    "MT": "Metallurgical Engineering",
    "NM": "Naval Architecture and Marine Engineering",
    "PE": "Petroleum Engineering",
    "PH": "Physics",
    "PI": "Production and Industrial Engineering",
    "ST": "Statistics",
    "TF": "Textile Engineering and Fibre Science",
    "XE": "Engineering Sciences",
    "XH": "Humanities and Social Sciences",
    "XL": "Life Sciences",
}
