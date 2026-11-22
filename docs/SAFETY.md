# Safety and commissioning

1. Confirm the physical circuit, EVSE and vehicle limits with a licensed electrician where required.
2. Keep maximum current at or below the commissioned Smappee limit.
3. Run Observe Only first and compare proposed current against grid, solar and battery behaviour.
4. Ensure EVCC and existing automations are disabled for the same charger entities before enabling live control.
5. Test fail-safe behaviour by temporarily making one critical sensor unavailable while Observe Only is active.
6. Use Force Charge only as a deliberate manual mode; it can charge during the peak window and may import from the grid.
7. The integration does not change AlphaESS modes, minimum SOC, charge schedules or Modbus registers.
