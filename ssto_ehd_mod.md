# Context: SSTO Project Pivot (The "Solid-State Wing" Update)
You are assisting me in updating my hard-engineering/sci-fi aerospace project: a single-stage-to-orbit (SSTO) spaceplane powered by a 1 GW continuous CHARM (p-11B) fusion reactor. I am currently kitbashing the heritage Space Shuttle FlightGear/Blender model to serve as a test article. 

My current systems-closure math (mass, power, water) is perfectly balanced, but I am changing the **physical mechanism of Stage 2** propulsion to incorporate real-world electrohydrodynamic (EHD) physics (inspired by the work of Jay Bowles/Plasma Channel, Ethan Krauss, and MIT). 

### The Lore & Engineering Physics (Read and Internalize)
*   **The Problem:** Bridging the "Ignorosphere" (15 km to 30+ km). Dense air is gone, vacuum is too far away. 
*   **The Old Design:** Stage 2 was an internal microwave air plasma jet.
*   **The New Design: Variable-State EHD Wings.** The wings *are* the engine. We are replacing the heritage Shuttle solid double-delta wings with a highly porous, flow-through aerodynamic grid (similar to a ramjet, but using electrodynamics instead of combustion).
*   **How Stage 2 Works:** The fusion plant's electrical bus drives nanosecond pulsed-power high-voltage to ultra-sharp razorblade emitters on the leading edges of the wing grid. This strips electrons and violently accelerates air through the wing toward variable-depth negative collectors, creating an immense "ionic wind" thrust. Variable collector spacing allows it to beat Paschen's Law and prevent arcing as atmospheric pressure drops.
*   **The Re-entry Solution (MHD Aerobraking):** An open, porous wing would vaporize instantly at Mach 25. Instead of heavy mechanical louvers closing the wing, the ship uses Magnetohydrodynamic (MHD) Aerobraking. Utilizing the fusion reactor's immense cryogenic and superconducting capacity, the wing's leading edges project a massive magnetic bow-shock. Because re-entry plasma is highly magnetic, this pushes the 3,000°F shockwave *around* the porous wing, acting as a massless, invisible heat shield while harvesting electrical power to top off flight batteries.

---

# Execution Plan
We need to surgically update the project without breaking the closed-form math equations. The 1 GW power budget and the 15-ton engine mass hole remain identical; we are simply reallocating how Stage 2 spends its 4.4t mass budget and 995 MW power allocation. 

Please execute the following plan step-by-step. Ask for my confirmation before moving between phases.

### Phase 1: Update the Paper (`arxiv.md`)
1.  **Section 1 & 2 (OML & Goals):** Update the "Heritage OML" constraint. The fuselage, belly TPS boat, and nose remain Shuttle-derived, but the wings are now explicitly described as "Porous Variable-State EHD/MHD Wings." Note that the shoulder scoops (former OMS pods) now *only* feed the Stage-1 Electric Ducted Fans (EDFs). 
2.  **Section 5 & 10.1 (Flight Regimes):** Change Stage 2 from "Microwave air plasma jet" to "Variable-State EHD Wing Array." Change its reaction mass from "Ingested + compressed air" to "Free stratospheric air (flow-through wing)."
3.  **Section 10.2 (Engine Mass Budget):** In Table 12, rename the 4.4t Stage 2 allocation from "MW farm + applicator + precompress" to "EHD Array & Pulsed-Power Capacitors."
4.  **Section 10.3 & 11 (Physical Envelope & TPS):** Add a paragraph explaining the MHD Aerobraking re-entry doctrine. Explain how the porous wing survives hypersonic re-entry by projecting a magnetic bow-shock, maintaining the "zero moving parts" solid-state philosophy. 

### Phase 2: Update the Assembly & Mass Models
1.  **`assembly.json`:** Modify the JSON hierarchy. Remove the Stage-2 internal ducting, microwave farm, and compressor nodes. Add nodes for "EHD Wing Grid," "Superconducting Leading Edges," and "Pulsed-Power Capacitors."
2.  **`constants_model.py`:** Ensure the 4.4t budget string for Stage 2 now points to the new EHD components. No changes to the total $m_{eng}$ or $\Delta v$ math are required.
3.  **Mermaid Diagrams:** Regenerate the `update_arxiv_mermaid.py` scripts to reflect the new parts list in the assembly outliner.

### Phase 3: Kitbashing the 3D Models (Blender & FlightGear)
1.  **Blender Modifications (`.blend` files):** Outline a Python script or manual checklist for me to modify the Shuttle wing mesh. The solid upper/lower surfaces of the double-delta wings need to be hollowed out into a radiator-like grid (longitudinal spars for strength, lateral high-voltage rails). The belly boat (black tiles) remains solid directly under the fuselage.
2.  **FlightGear XML Integration (`.xml` configs):** Update the engine thrust application in FG. Stage 2 thrust is no longer a point-source at the aft nozzle; write a snippet to distribute the Stage 2 thrust vector laterally across the left and right wing areas. 
3.  **FlightGear Aerodynamics:** Add a custom nasal script or JSBSim aerodynamic modifier. We need drag to drastically increase when the MHD shield is activated during re-entry (simulating the magnetic bow-shock acting as an airbrake). 

Acknowledge this prompt, summarize your understanding of the "solid-state wing" concept, and let me know when you are ready to begin Phase 1 on `arxiv.md`.