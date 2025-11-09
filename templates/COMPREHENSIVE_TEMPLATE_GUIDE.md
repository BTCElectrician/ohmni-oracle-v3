# Comprehensive Template System - What You Can Capture

## 🎯 Philosophy

**One template to rule them all.** Whether it's:
- Office building
- Hospital
- Data center
- Lab/Research facility
- Food service
- Educational facility
- Mixed-use

...the chatbot asks relevant questions and skips what doesn't apply.

---

## 📋 Electrical Template - System by System

### **Power Systems** (Your Original + Enhanced)
- **Circuits**: Normal, emergency, critical, UPS-backed
- **Outlets**: Regular, controlled, GFCI, USB, floor, isolated ground, hospital-grade, red (emergency)
- **Fixtures**: All types + emergency fixtures + exit signs
- **Switches**: Count, type (dimmer/occupancy/daylight), location

**Chatbot Example:**
```
Bot: "Room C4, ICU patient room. What circuits?"
Foreman: "Lighting L12, power P8, red outlets on circuit ER-4"
Bot: "How many red outlets?"
Foreman: "4, one per wall"
Bot: "Got it. Hospital-grade required?"
Foreman: "Yes"
Bot: "Saved. 4 hospital-grade red outlets on ER-4."
```

---

### **Fire Alarm / Life Safety** (NEW)
Everything the fire marshal cares about:

| Device | What to Capture | Example |
|--------|----------------|---------|
| Smoke Detectors | Count, type, locations | "2 photoelectric, ceiling mount" |
| Heat Detectors | Count, type, locations | "1 fixed temp, 135°F in kitchen" |
| Pull Stations | Count, locations | "1 by exit door" |
| Horn/Strobes | Count, type, locations | "2 wall-mount horn/strobes" |
| Strobes Only | Count (for high-noise areas) | "3 strobes in mechanical room" |
| Speakers | Count, type | "4 ceiling speakers, voice evac" |

Plus: Panel zone, circuit, notes

**Chatbot Example:**
```
Foreman: "Room B2, conference room. Fire alarm check."
Bot: "What devices?"
Foreman: "One smoke detector center of ceiling, one horn strobe by door"
Bot: "What zone?"
Foreman: "Zone 3, circuit FA-12"
Bot: "Saved. Smoke + horn/strobe on Zone 3."
```

---

### **Data/Telecom** (NEW)
Modern buildings = heavy data:

- Data outlets (RJ45)
- Phone outlets
- Fiber outlets
- Floor boxes vs wall boxes
- Wireless AP locations
- Home-run to which patch panel

**Chatbot Example:**
```
Foreman: "Room D5, open office area"
Bot: "How many workstations?"
Foreman: "12"
Bot: "Data drops per station?"
Foreman: "2 each, floor boxes"
Bot: "24 data outlets in floor boxes. Wireless AP?"
Foreman: "Yes, ceiling mount center of room"
Bot: "Saved. Home run to which patch panel?"
Foreman: "IDF-2, panel B"
Bot: "Got it. Tagged to IDF-2B."
```

---

### **Security Systems** (NEW)
Big buildings need security:

- Cameras (count, type, PTZ or fixed, locations)
- Card readers (doors with access control)
- Door contacts (which doors monitored)
- Motion detectors
- Panic buttons
- Intercom

**Chatbot Example:**
```
Foreman: "Room E1, main lobby. Security check."
Bot: "Cameras?"
Foreman: "Two PTZ cameras, corners"
Bot: "Card readers?"
Foreman: "One at the reception desk door"
Bot: "Panic button?"
Foreman: "Yes, under reception desk"
Bot: "Saved. 2 PTZ cameras, 1 card reader, 1 panic button."
```

---

### **Audiovisual** (NEW)
Conference rooms, auditoriums, classrooms:

- Displays (count, sizes, locations)
- Projectors
- Speakers (ceiling, wall, type)
- Microphones (wired, wireless, lapel)
- Control panels (touch screens)
- Wall plates (HDMI, VGA, USB)
- Equipment rack location

**Chatbot Example:**
```
Foreman: "Room F3, training room. AV check."
Bot: "Displays?"
Foreman: "One 85-inch display, front wall"
Bot: "Speakers?"
Foreman: "Four ceiling speakers, surround"
Bot: "Microphones?"
Foreman: "Two wireless lapel, one podium"
Bot: "Control panel?"
Foreman: "Yes, Crestron touch screen by door"
Bot: "Wall plates?"
Foreman: "Two HDMI at conference table"
Bot: "Saved. Want me to generate AV riser diagram?"
```

---

### **Nurse Call** (NEW - Healthcare)
Hospitals, nursing homes, assisted living:

- Stations (bedside, bathroom, types)
- Pull cords (bathroom emergency)
- Dome lights (hall indication)
- Code Blue buttons (emergency)

**Chatbot Example:**
```
Foreman: "Room G2, patient room. Nurse call."
Bot: "Stations?"
Foreman: "Bedside station, bathroom station"
Bot: "Pull cord in bathroom?"
Foreman: "Yes"
Bot: "Dome light outside door?"
Foreman: "Yes, red/white"
Bot: "Code Blue button?"
Foreman: "Yes, headwall"
Bot: "Saved. Full nurse call package installed."
```

---

### **Medical Gas** (NEW - Healthcare)
Critical for hospitals, dental, vet:

- Oxygen
- Vacuum (medical suction)
- Medical air
- Nitrous oxide
- WAGD (Waste Anesthesia Gas Disposal)
- Alarm panels

**Chatbot Example:**
```
Foreman: "Room H1, OR-3. Medical gas check."
Bot: "What gases?"
Foreman: "Oxygen, vacuum, medical air, WAGD"
Bot: "How many of each?"
Foreman: "Two outlets each on headwall, one vacuum at foot"
Bot: "Alarm panel?"
Foreman: "Yes, zone 3"
Bot: "Saved. 2 O2, 3 VAC, 2 MedAir, 2 WAGD, alarm Zone 3."
```

---

### **Lab Systems** (NEW - Research/Science)
Labs, clean rooms, research facilities:

- Fume hoods
- Biosafety cabinets
- Lab gases (nitrogen, argon, CO2, etc.)
- Emergency showers
- Eye wash stations
- DI water
- Compressed air
- Vacuum

**Chatbot Example:**
```
Foreman: "Room J4, chemistry lab. Lab systems."
Bot: "Fume hoods?"
Foreman: "Two, 8-foot walk-in"
Bot: "Lab gases?"
Foreman: "Nitrogen, argon, compressed air to benches"
Bot: "Emergency equipment?"
Foreman: "Shower and eye wash by exit"
Bot: "Saved. 2 fume hoods, 3 gas types, emergency equipment."
```

---

### **Data Center** (NEW - IT/Telecom)
Critical for server rooms, data centers:

- Rack count
- PDU types
- UPS-fed vs generator-fed
- CRAC/CRAH (cooling)
- Environmental monitoring
- Leak detection
- EPO (Emergency Power Off) button

**Chatbot Example:**
```
Foreman: "Room K1, main data center. Data center check."
Bot: "How many racks?"
Foreman: "24 racks, 42U each"
Bot: "PDU type?"
Foreman: "Dual-feed intelligent PDUs, 30A"
Bot: "Power sources?"
Foreman: "UPS and generator backed"
Bot: "Cooling?"
Foreman: "Six CRAC units, in-row"
Bot: "Environmental monitoring?"
Foreman: "Yes, temp/humidity sensors every 4 racks"
Bot: "EPO button?"
Foreman: "Yes, by main entrance"
Bot: "Saved. 24 racks, dual-PDU, full redundancy."
```

---

### **Kitchen Systems** (NEW - Food Service)
Restaurants, cafeterias, commercial kitchens:

- Hood suppression (Ansul/other)
- Grease trap alarm
- Gas detection
- Refrigeration alarms

**Chatbot Example:**
```
Foreman: "Room L1, main kitchen. Kitchen systems."
Bot: "Hood suppression?"
Foreman: "Ansul system, two zones"
Bot: "Grease trap alarm?"
Foreman: "Yes, connected to BMS"
Bot: "Gas detection?"
Foreman: "Natural gas detector by range"
Bot: "Walk-in alarms?"
Foreman: "Two walk-in coolers, both have high-temp alarms"
Bot: "Saved. Full kitchen safety systems."
```

---

## 📐 Architectural Template - System by System

### **Dimensions & Walls** (Your Original + Enhanced)
- Walls by orientation (N/S/E/W) + types
- Wall details (fire rating, STC, stud type)
- Dimensions, square footage, ceiling heights

### **Doors & Windows** (NEW - Comprehensive)
- Door counts, numbers, types, hardware
- Fire-rated doors
- Access control integration
- Window types, sizes, treatments

### **Finishes** (Enhanced)
Now broken down by:
- **Floor**: Material, color, base, transitions
- **Walls**: Material, color, wainscot, corner guards, wall protection
- **Ceiling**: Type, grid, height, access panels

### **Casework & Specialties** (NEW)
Everything that's not structure:
- Base/wall cabinets
- Countertops
- Sinks
- Toilet accessories
- Signage
- Whiteboards/tack boards
- Mirrors
- Grab bars
- Shelving
- Lockers

**Chatbot Example:**
```
Foreman: "Room M2, breakroom. Specialties check."
Bot: "Casework?"
Foreman: "8 feet of base cabinets, 6 feet of uppers"
Bot: "Countertop?"
Foreman: "Laminate, single sink"
Bot: "Appliances?"
Foreman: "Refrigerator, microwave, coffee maker"
Bot: "Saved. Standard breakroom package."
```

---

### **Code & Compliance** (NEW)
Track what inspectors care about:

**ADA/Accessibility:**
- ADA required?
- Accessible route?
- Turning radius clear?
- Accessible hardware?
- Proper signage?

**Fire/Life Safety:**
- Fire rating required
- Fire/smoke dampers
- Firestopping locations
- Occupancy classification
- Means of egress

**Acoustics:**
- STC requirements
- CAC requirements
- Sound masking
- Acoustic treatment

**Chatbot Example:**
```
Foreman: "Room N3, private office. Code compliance."
Bot: "ADA requirements?"
Foreman: "Yes, fully accessible"
Bot: "Fire rating?"
Foreman: "1-hour on corridor wall"
Bot: "Acoustic requirements?"
Foreman: "STC 45 on all walls"
Bot: "Saved. ADA, 1-hr FR, STC 45."
```

---

### **Special Room Types** (NEW)
Pre-configured room packages:

**Clean Room:**
- Classification (ISO 5, 6, 7, etc.)
- Wall/ceiling/floor systems
- Pass-throughs
- Air showers
- Differential pressure monitors

**Lab:**
- Casework type
- Fume hoods
- Biosafety cabinets
- Epoxy floors
- Chemical-resistant walls

**Food Service:**
- Quarry tile
- FRP walls
- Coved base
- Grease-resistant
- Hood systems
- Walk-in coolers/freezers

**Data Center:**
- Raised floor (height)
- Cable tray
- Hot aisle/cold aisle
- Containment systems

**Operating Room:**
- OR number
- Size
- Ceiling height
- Surgical lights
- Booms
- Lead lining
- Control vestibule
- Adjacent scrub sink

**Chatbot Example:**
```
Foreman: "Room O1, OR-1. Special room check."
Bot: "OR size?"
Foreman: "20 by 20, 12-foot ceiling"
Bot: "Surgical lights?"
Foreman: "Two main, one aux"
Bot: "Booms?"
Foreman: "One anesthesia, one surgical"
Bot: "Lead lining?"
Foreman: "No, this is general surgery"
Bot: "Control vestibule?"
Foreman: "Yes, with scrub sink adjacent"
Bot: "Saved. OR-1 configured as general surgery suite."
```

---

## 🚀 Why This Works

### **1. Chatbot Knows Context**
```
Foreman: "Room P5, patient room"
Bot: [Knows to ask about nurse call, medical gas, hospital-grade outlets]

Foreman: "Room Q2, conference room"
Bot: [Knows to ask about AV, power/data, finishes]

Foreman: "Room R3, data closet"
Bot: [Knows to ask about racks, cooling, power density]
```

### **2. Smart Defaults**
```
Bot: "Room type?"
Foreman: "Standard office"
Bot: "Applied office template: 2 data, 4 outlets, standard finishes. Anything different?"
Foreman: "Add a TV and 2 USBs"
Bot: "Updated. Office + AV package."
```

### **3. Copy/Propagate**
```
Foreman: "Rooms 201 through 212 are all identical"
Bot: "Copy Room 201 template to 202-212?"
Foreman: "Yes"
Bot: "Done. 12 rooms configured in 3 seconds."
```

### **4. Field Intelligence Capture**
Every template has:
- **Discrepancies**: Drawing vs field
- **Field notes**: What foreman observed
- **Photos**: Visual documentation
- **Coordination issues**: MEP conflicts
- **Owner requests**: Change orders

```
Foreman: "Room S4 has a coordination issue"
Bot: "Describe it"
Foreman: "Duct conflicts with beam. Need to reroute."
Bot: "Logged. Flag for engineer review?"
Foreman: "Yes, high priority"
Bot: "Created RFI-0187. Added photo prompt."
Foreman: [Takes photo]
Bot: "Photo attached to RFI. Notifying MEP engineer."
```

---

## 📊 What You Get

### **For Every Room:**
- Complete electrical inventory
- Complete architectural specification
- All low-voltage systems
- All life safety systems
- All special systems
- Code compliance checklist
- Field intelligence
- Photos
- Foreman signature
- Timestamp

### **For Every Project:**
- 100% room-by-room documentation
- Query: "Show all rooms missing fire alarm devices"
- Query: "Which rooms need ADA compliance?"
- Query: "Generate equipment cut sheet list"
- Query: "Which rooms has foreman flagged issues?"

---

## 🎤 Voice Workflow Example (Full Room)

```
Foreman: "New room, A304"
Bot: "Room type?"
Foreman: "Conference room"
Bot: "Got it. Conference room A304. Floor?"
Foreman: "Level 3, sheet A3.01"
Bot: "Starting walkthrough. Electrical first. Lighting circuits?"
Foreman: "L28 and L29, dimmable"
Bot: "Outlets?"
Foreman: "10 wall, 4 floor in conference table, 2 USBs"
Bot: "Data?"
Foreman: "6 data drops in table, 1 wireless AP"
Bot: "AV?"
Foreman: "One 86-inch display, 4 ceiling speakers, Crestron panel, 2 HDMI at table"
Bot: "Fire alarm?"
Foreman: "One smoke, one horn-strobe"
Bot: "Finishes. Floor?"
Foreman: "Carpet tile CT-3"
Bot: "Walls?"
Foreman: "Paint PT-2, north wall has whiteboard"
Bot: "Ceiling?"
Foreman: "ACT 2x2, 9 feet"
Bot: "HVAC?"
Foreman: "4 supply diffusers, 2 returns, one wall thermostat"
Bot: "Any discrepancies?"
Foreman: "Drawing shows 8 outlets, installed 10 per owner request"
Bot: "Logged as owner request. Ready to sign off?"
Foreman: "Yes"
Bot: "Room A304 signed off by jfernandez at 3:42pm. Want photo?"
Foreman: "Yes" [takes photo]
Bot: "Saved. Next room?"
```

**Time: 90 seconds. Completeness: 100%.**

---

## Files Created

1. **`e_rooms_template_v2.json`** - Complete electrical template
2. **`a_rooms_template_v2.json`** - Complete architectural template
3. **This guide** - System-by-system breakdown

**This is your competitive moat. Nobody else has this.**

