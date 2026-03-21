# Data Cleaning Directory

This directory contains all scripts and tools used to clean and process raw POST data from state agencies.

## Standardized Data Schema

All cleaned data must conform to the following TypeScript interface, which defines the columns configured to render on the front-end:

```typescript
export interface PoliceOfficer {
  // core fields
  agency_name: string;                    // Name of the employing agency
  start_date: string;                     // Employment start date (YYYY-MM-DD)
  end_date: string;                       // Employment end date (YYYY-MM-DD)
  full_name: string;                      // Complete name
  first_name: string;                     // First name
  last_name: string;                      // Last name
  person_nbr: string;                     // Unique person identifier
  state: string;                          // State abbreviation (lowercase)

  // Optional fields
  rank: string;                           // Officer rank/title
  middle_name: string;                    // Middle name
  current_certificate_status: string;     // Current certification status
  position?: string;                      // Position title
  status?: string;                        // Employment status
  notes?: string;                         // Additional notes
  offense?: string;                       // Disciplinary offense
  sanction?: string;                      // Sanction imposed
  violation?: string;                     // Type of violation
  sanction_date?: string;                 // Date of sanction (YYYY-MM-DD)
  separation_reason?: string;             // Reason for separation
  employment_status?: string;             // Current employment status
  certification_type?: string;            // Type of certification
  type?: string;                          // Officer type (police/corrections)

  // Extensibility
  [key: string]: any;                     // Allow for state-specific fields
}
```

### Key Schema Notes

1. **Dates:** Must be in `YYYY-MM-DD` format
2. **State:** Use lowercase two-letter abbreviation (e.g., `ca`, `tx`)
3. **Names:** Properly parsed into `first_name`, `middle_name`, `last_name`, and combined `full_name`
4. **Identifiers:** Both `person_nbr`
5. **Optional Fields:** Include when available in source data
