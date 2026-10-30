"""Domain event-management knowledge engine for FestOS AI.

Provides expert guidance on college festivals, hackathons, operational logistics,
checklists, crowd control, volunteer allocation, and contingency planning.
Answers general event questions without requiring database/vector matches,
and supplies actionable recommendations for hybrid operational queries.
"""
import re
from typing import Any, Optional


def get_general_event_advice(query: str, history: Optional[list[dict[str, Any]]] = None) -> str:
    """Generates structured, expert event-planning knowledge tailored to user query and multi-turn context."""
    norm = query.lower().strip()

    # Context extraction from conversation history
    context_notes = []
    has_twoday_context = False
    volunteers_count = None
    students_count = None

    if history:
        for h in history:
            c = str(h.get("content", "")).lower()
            if "two-day" in c or "2-day" in c or "two day" in c:
                has_twoday_context = True
            m_stud = re.search(r"(\d+)\s*(students|participants|attendees)", c)
            if m_stud:
                students_count = int(m_stud.group(1))
            m_vol = re.search(r"(\d+)\s*volunteers", c)
            if m_vol:
                volunteers_count = int(m_vol.group(1))

    # 1. Festival / Event Planning Checklist
    if "checklist" in norm:
        return (
            "### Comprehensive College Festival Operational Checklist\n\n"
            "A successful festival requires methodical preparation across key operational pillars:\n\n"
            "1. **Venue & Infrastructure**\n"
            "   - Campus administrative permissions, auditorium/ground bookings, and noise permits.\n"
            "   - Stage setup, generator backups (diesel generators for stage & lighting), and rainproofing.\n"
            "   - Restroom cleanliness, sanitation stations, and waste segregation bins.\n\n"
            "2. **Registration & Crowd Management**\n"
            "   - Pre-registration validation, on-spot desk layout, and barcode/wristband issuance.\n"
            "   - Clear barricading for queues, holding zones, and separate entrance/exit channels.\n\n"
            "3. **Scheduling & Run-of-Show**\n"
            "   - Master schedule with minimum 30-minute buffers between consecutive stage performances.\n"
            "   - Minute-by-minute run-of-show cue sheets for stage managers, audio engineers, and emcees.\n\n"
            "4. **Volunteers & Staffing**\n"
            "   - Core teams: Stage Operations, Registration, Hospitality, Logistics, Security, and Media.\n"
            "   - Shift scheduling (4–6 hour rotations), volunteer identification badges, and walkie-talkies.\n\n"
            "5. **Accommodation & Hospitality**\n"
            "   - Separate hostel/hotel wings for male and female contingents with 24/7 security.\n"
            "   - Transit shuttles between off-campus accommodations and the primary festival venue.\n\n"
            "6. **Audio-Visual & Technical Equipment**\n"
            "   - Microphones (wireless, podium, lapel), sound checks, stage lighting, and PA systems.\n"
            "   - Dedicated tech booth with backup power (UPS) for mixers and display LED walls.\n\n"
            "7. **Safety, Medical & Contingency**\n"
            "   - On-site ambulance, first-aid station staffed by paramedics, and clear emergency fire exits.\n"
            "   - Crowd dispersal protocol, emergency contact directory, and rapid incident escalation matrix."
        )

    # 2. Planning a College Festival (Master Guide)
    if "how should i plan a college festival" in norm or "plan a college festival" in norm or "organize a college festival" in norm:
        return (
            "### Strategic Guide: Planning a Successful College Festival\n\n"
            "Planning an inter-college cultural festival involves six structured phases:\n\n"
            "1. **Foundation & Charter (Months 1–2)**\n"
            "   - Form the core organizing committee (Festival Director, Logistics, Events, Hospitality, Finance, PR).\n"
            "   - Define theme, target attendance, festival dates, and draft the operating budget.\n"
            "   - Secure institutional administration approvals and campus venue reservations.\n\n"
            "2. **Program Architecture & Scheduling (Month 3)**\n"
            "   - Curate flagship competitions (Battle of Bands, Dance, Drama, Hackathon, Debates).\n"
            "   - Build a balanced schedule preventing sound bleed between acoustic and high-decibel stages.\n"
            "   - Incorporate 30–45 minute setup/teardown buffers between events in shared venues.\n\n"
            "3. **Logistics & Hospitality Preparation (Month 4)**\n"
            "   - Audit campus hostel bed availability and negotiate discounted partner hotel blocks.\n"
            "   - Issue vendor RFPs for stage construction, lighting, sound, generators, and catering.\n"
            "   - Implement an event management system (like FestOS) for participant registration and room allocation.\n\n"
            "4. **Volunteer Onboarding & Briefings (Month 5)**\n"
            "   - Recruit student volunteers into dedicated functional verticals.\n"
            "   - Conduct dry-run walkthroughs for crowd flow, registration bottlenecks, and emergency exits.\n\n"
            "5. **Execution & Live Operations (Festival Days)**\n"
            "   - Establish a Central Operations Control Center to monitor venue capacities, delays, and incidents.\n"
            "   - Execute morning briefing sessions and nightly debriefs with vertical leads.\n\n"
            "6. **Post-Festival Wrap-up**\n"
            "   - Vendor settlements, inventory reconciliation, return of rented equipment, and attendee feedback surveys."
        )

    # 3. Hackathon Schedule / Two-Day Program
    if "hackathon" in norm and ("schedule" in norm or "plan" in norm or "two-day" in norm or "timeline" in norm):
        return (
            "### Recommended 36-Hour Two-Day Hackathon Schedule\n\n"
            "**Day 1: Ideation, Kickoff & Development**\n"
            "- **08:30 – 10:00**: Check-in, badge distribution, and breakfast.\n"
            "- **10:00 – 11:00**: Opening ceremony, keynote address, and problem statement reveal.\n"
            "- **11:00**: **Hacking Begins!** Team workspace setup and architecture design.\n"
            "- **13:30 – 14:30**: Lunch buffet.\n"
            "- **15:30 – 17:30**: **Mentor Checkpoint 1**: Industry mentors review problem viability and git repos.\n"
            "- **20:00 – 21:00**: Dinner served.\n"
            "- **23:00 – 23:30**: Midnight snack, coffee rush, and mini entertainment break.\n\n"
            "**Day 2: Refinement, Judging & Finale**\n"
            "- **03:00 – 04:00**: Optional late-night technical debug clinic.\n"
            "- **07:30 – 08:30**: Breakfast and refresh.\n"
            "- **09:30 – 11:30**: **Mentor Checkpoint 2**: Polish features, prepare pitch decks, and test demos.\n"
            "- **12:00**: **Code Freeze & Final Project Submission**.\n"
            "- **12:15 – 13:30**: Lunch.\n"
            "- **13:30 – 15:30**: **Preliminary Expo / Booth Judging**: All teams present to roving evaluation panels.\n"
            "- **16:00 – 17:15**: **Top 5 Finalist Stage Pitches** (5-min pitch + 3-min judge Q&A).\n"
            "- **17:30 – 18:00**: Award ceremony, sponsor recognition, and closing remarks."
        )

    # 4. Volunteer Organization & Multi-turn Staffing
    if "volunteer" in norm and ("organize" in norm or "structure" in norm or "manage" in norm or "shift" in norm or "how should" in norm):
        context_intro = ""
        if has_twoday_context or students_count or volunteers_count:
            specs = []
            if has_twoday_context:
                specs.append("2-day festival format")
            if students_count:
                specs.append(f"{students_count} participants")
            if volunteers_count:
                specs.append(f"{volunteers_count} volunteers")
            context_intro = f"*Tailored for your {', '.join(specs)}:*\n\n"

        ratio_guidance = ""
        if volunteers_count and students_count:
            ratio = students_count // volunteers_count
            ratio_guidance = (
                f"- **Staffing Ratio**: At ~1 volunteer per {ratio} participants, resources are lean. "
                "Centralize high-traffic points (Registration & Main Stage) and stagger volunteer breaks carefully.\n\n"
            )

        return (
            f"### Volunteer Organization & Operational Structure\n\n"
            f"{context_intro}"
            f"{ratio_guidance}"
            "1. **Organize into Functional Verticals**\n"
            "   - **Registration & Info Hub**: Manages check-in lines, welcome kits, and general attendee queries.\n"
            "   - **Stage & Green Room Logistics**: Assists stage managers, handles mic handoffs, and guides performers.\n"
            "   - **Hospitality & Accommodation**: Welcomes outstation contingents, oversees hostel check-ins, and coordinates shuttles.\n"
            "   - **Crowd Control & Security Liaisons**: Monitors auditorium doors, prevents bottlenecking, and guards restricted zones.\n"
            "   - **Food & Catering Oversight**: Verifies meal coupons, checks vendor cleanliness, and distributes volunteer water/meals.\n\n"
            "2. **Shift Scheduling Best Practices**\n"
            "   - Divide the day into two primary shifts (e.g., Morning 08:00–14:30, Evening 14:00–21:00) with a 30-minute handover overlap.\n"
            "   - Keep a floating reserve (15–20% of your volunteer pool) on standby for sudden surges or absences.\n\n"
            "3. **Communication & Command Chain**\n"
            "   - Assign one dedicated Student Lead per vertical with a walkie-talkie connecting directly to the Control Center.\n"
            "   - Establish a dedicated volunteer rest area with hydration, charging docks, and emergency first-aid."
        )

    # 5. Queue Management & Overcrowding Mitigation
    if "queue" in norm or "overcrowd" in norm or "crowd" in norm:
        return (
            "### Crowd Control & Registration Queue Management Strategies\n\n"
            "To prevent long queues and eliminate dangerous overcrowding:\n\n"
            "1. **Pre-Arrival Digital Fast-Tracks**\n"
            "   - Send QR check-in codes to attendees prior to festival morning.\n"
            "   - Split desks alphabetically or by contingent ID (e.g., Desks 1–2 for C01–C15, Desks 3–4 for C16–C30, Desks 5–6 for spot registrations).\n\n"
            "2. **Physical Queue Architecture**\n"
            "   - Deploy serpentine (snake) stanchion barriers to guide single-file flow and prevent line-cutting.\n"
            "   - Create a designated holding/waiting pen outside the registration lobby so indoor areas never exceed fire safety limits.\n\n"
            "3. **Separate Ingress and Egress**\n"
            "   - Enforce strict one-way movement: entry through dedicated doors, exit through distinct pathways.\n"
            "   - Station volunteers at venue double-doors to prohibit incoming traffic through exit gates.\n\n"
            "4. **Real-time Auditorium Thresholds**\n"
            "   - Implement a 'one-in, one-out' clicker count once an auditorium reaches 85% seating capacity.\n"
            "   - Broadcast live overflow feeds to secondary outdoor screens or seminar rooms for headline acts."
        )

    # 6. Accommodation Planning (e.g., for 500 participants or general)
    if "accommodation" in norm and ("500" in norm or "estimate" in norm or "how should we" in norm or "organize" in norm or "arrange" in norm):
        return (
            "### Accommodation Planning & Logistics Framework (e.g. 500 Participants)\n\n"
            "When organizing accommodation for 500 festival participants, apply these proven operational guidelines:\n\n"
            "1. **Capacity Sizing & Contingency Buffer**\n"
            "   - **Base Demand**: 500 beds requested.\n"
            "   - **Safety Buffer**: Add a 10% contingency buffer (~50 extra beds) to absorb last-minute contingent additions, judges, and core team emergencies (target total: ~550 beds).\n"
            "   - **Demographic Split**: Standardize on gender-segregated blocks based on verified registrations (e.g. 300 male beds / 200 female beds).\n\n"
            "2. **Hostel vs. External Stay Allocation**\n"
            "   - **On-Campus Hostels (Preferred)**: Reserve campus hostel beds for competitive contingents needing early morning or late-night access to venues.\n"
            "   - **Off-Campus Partner Hotels/Lodges**: Group complete colleges together at external properties to keep contingents unified and simplify bus coordination.\n\n"
            "3. **Transit & Commute Logistics**\n"
            "   - Contract dedicated shuttle buses running fixed 30-minute loops between external partner stays and campus.\n"
            "   - Schedule early morning express shuttles before 08:30 AM and late-night return trips after the final concert.\n\n"
            "4. **Reception & Safety Protocols**\n"
            "   - Establish a 24/7 Central Hospitality Helpdesk at the campus entrance to verify IDs and hand over room keys.\n"
            "   - Deploy resident security guards and female wardens at female accommodation wings.\n"
            "   - Note: In FestOS, always run the automated allocation engine (`POST /allocations/generate`) to balance cost and proximity."
        )

    # 7. Internal vs External Accommodation Comparison
    if "internal" in norm and "external" in norm and "accommodation" in norm:
        return (
            "### Comparison: Internal vs. External Festival Accommodation\n\n"
            "| Operational Factor | Internal Accommodation (Hostels) | External Accommodation (Hotels/Lodges) |\n"
            "| :--- | :--- | :--- |\n"
            "| **Proximity & Commute** | On-campus; 5-minute walk to venues. Zero transit delays or bus costs. | 2–10 km away; requires contracted shuttle transport and scheduled pick-ups. |\n"
            "| **Operational Cost** | Highly economical; institutional maintenance fees only. | Commercial bed rates apply; requires advance deposits and cancellation policies. |\n"
            "| **Access & Curfew** | Governed by university hostel rules and warden security sign-ins. | More flexible check-in hours, but requires dedicated security chaperone protocol. |\n"
            "| **Best Suited For** | Large student contingents, volunteers, and budget-conscious participants. | Celebrity performers, external judges, VIP guests, and overflow contingent leaders. |\n\n"
            "**Operational Best Practice**: Maximize on-campus hostel occupancy first using the FestOS `min_cost` engine preset, then contract external hotel blocks with a 10% safety buffer for overflow."
        )

    # 8. Run-of-Show Document Guidance
    if "run-of-show" in norm or "run of show" in norm:
        return (
            "### What is a Run-of-Show Document?\n\n"
            "A **Run-of-Show (ROS)** is an authoritative, minute-by-minute operational cue sheet used by the event director, stage manager, sound/lighting engineers, and emcees to execute an event flawlessly.\n\n"
            "#### Essential Columns in a Run-of-Show Table:\n"
            "1. **Item / Cue #**: Sequential reference identifier (e.g., C-01, C-02).\n"
            "2. **Scheduled Time**: Exact wall-clock time (e.g., 10:00 AM – 10:05 AM).\n"
            "3. **Duration**: Time allotted for the segment (e.g., 5 mins).\n"
            "4. **Segment Name / Action**: What is happening on stage (e.g., 'Welcome Address by Dean').\n"
            "5. **Audio / Mic Cue**: Which microphones are active (e.g., 'Podium Mic 1 ON, Walk-on BGM fade out').\n"
            "6. **Visual / Lighting Cue**: Lighting state (e.g., 'Main stage spotlight, screen logo preset 2').\n"
            "7. **Lead In-Charge**: Specific core team member responsible for cue execution.\n\n"
            "**Key Value**: It synchronizes backstage crews, prevents dead-air pauses, and ensures tight adherence to venue curfews."
        )

    # 9. Preventing Scheduling Conflicts
    if "prevent" in norm and ("conflict" in norm or "clash" in norm or "scheduling" in norm):
        return (
            "### How to Prevent and Mitigate Event Scheduling Conflicts\n\n"
            "To build a resilient festival schedule free of venue and personnel clashes:\n\n"
            "1. **Enforce Turnaround Buffers (Assumption A-11)**\n"
            "   - Never schedule events back-to-back in the same venue without at least a 30-minute buffer for stage clearance, AV reset, and audience transit.\n\n"
            "2. **Acoustic & Venue Isolation**\n"
            "   - Separate high-decibel performances (e.g., Battle of Bands, Western Music) from quiet acoustic or speaking events (e.g., Debates, Classical Solo, Quiz) into distant buildings to prevent sound bleed.\n\n"
            "3. **Participant Cross-Clash Checks**\n"
            "   - Avoid scheduling preliminary rounds of overlapping categories (e.g., Literary events and Fine Arts) concurrently if participants frequently cross-register.\n\n"
            "4. **Volunteer Shift Bounds (Assumption A-16)**\n"
            "   - Ensure volunteer coordinators are not assigned to concurrent events occurring in different venues. Keep assignments venue-centric rather than event-centric."
        )

    # 10. Vendor Management Best Practices
    if "vendor" in norm and ("best practice" in norm or "manage" in norm or "compliance" in norm):
        return (
            "### Best Practices for Festival Vendor Management\n\n"
            "1. **Pre-Event Compliance & Certification**\n"
            "   - Mandatory verification of food hygiene/safety licenses (e.g., FSSAI certification expiry dates) before stall allocation.\n"
            "   - Require fire safety clearance certificates for vendors operating gas burners or high-draw electrical equipment.\n\n"
            "2. **Dietary Coverage Assurance**\n"
            "   - Require food court menus to explicitly provide verified Vegetarian, Jain, Vegan, and Halal meal options.\n"
            "   - Pre-agree on subsidized festival meal vouchers for participants and volunteers.\n\n"
            "3. **Utility & Infrastructure Delivery**\n"
            "   - Provide designated electrical power drops with individual circuit breakers to avoid overloading venue transformers.\n"
            "   - Arrange dedicated fresh water lines and greywater drainage points.\n\n"
            "4. **Clear Commercial & Settlement Terms**\n"
            "   - Set contractual payment milestones: 40% advance upon contract signing, 40% on delivery, and 20% final balance post-festival upon waste cleanup sign-off."
        )

    # 11. Festival Start Time Guidance
    if ("what time should" in norm or "when should" in norm) and ("start" in norm or "begin" in norm) and "festival" in norm:
        return (
            "### Strategic Festival Start Time Recommendations\n\n"
            "The ideal start time for a college festival depends on your program architecture, audience transit, and local sound regulations:\n\n"
            "1. **Recommended Start Window: 09:00 AM – 10:00 AM**\n"
            "   - **08:00 AM – 09:30 AM**: Registration desks open, outstation contingents complete check-in, and judges arrive for orientation.\n"
            "   - **09:30 AM – 10:30 AM**: Official Inauguration ceremony, dignitary speeches, and festival anthem release.\n"
            "   - **10:30 AM Onward**: Parallel competition tracks commence across auditorium and seminar venues.\n\n"
            "2. **Key Operational Considerations**\n"
            "   - **Attendee Commute**: Avoid starting before 09:00 AM if attendees rely on early morning public transit or suburban trains.\n"
            "   - **Evening Headline Curfew**: Most campuses enforce a 10:00 PM sound curfew. Starting daytime events by 10:00 AM ensures stage competitions conclude by 06:00 PM, leaving ample time for the headline celebrity concert."
        )

    # Default Comprehensive Event Advisory
    return (
        "### Expert Event Management Recommendations\n\n"
        "To deliver a seamless festival experience:\n\n"
        "1. **Operational Planning & Buffers**: Maintain 30-minute setup and teardown buffers between scheduled items to avoid cascading delays.\n"
        "2. **Logistics & Infrastructure**: Ensure dedicated power backups, backup wireless microphones, and reliable crowd barrier channels.\n"
        "3. **Hospitality & Safety**: Provide clear signage, emergency medical stations with paramedics, and 24/7 assistance desks for outstation contingents.\n"
        "4. **Control Center Coordination**: Centralize communications through an Operations Control Center to monitor venue capacities and resolve incidents in real time."
    )
