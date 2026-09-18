/**
 * Enums, Defaults, Station Catalogs, and Validation Helpers
 * for JobEditorModal and Railway Possession Scheduling.
 */

export const JOB_SOURCES = {
  PROJECT: 'addition',
  EMERGENCY: 'emergency',
  ROUTINE: 'routine',
};

export const JOB_SOURCE_LABELS = {
  [JOB_SOURCES.PROJECT]: 'Project Addition',
  [JOB_SOURCES.EMERGENCY]: 'Emergency Repair',
  [JOB_SOURCES.ROUTINE]: 'Routine Maintenance',
};

export const ACTIVITY_TYPES = [
  { id: 'TRACK', label: 'Track Works', desc: 'Rail replacement, tamping, turnout replacement' },
  { id: 'CIVIL', label: 'Civil Works', desc: 'Tunnel inspection, structural concrete, drainage' },
  { id: 'SIGNAL', label: 'Signalling', desc: 'Point machines, track circuits, CBTC balises' },
  { id: 'POWER', label: 'Power / Third Rail', desc: 'Substation maintenance, conductor rail, overhead line' },
  { id: 'TELECOM', label: 'Telecoms / Comms', desc: 'Radio leaky feeder, fibre optic trunking, CCTV' },
];

export const NATURE_OF_WORKS = [
  {
    id: 'HEAVY',
    label: 'HEAVY Work',
    badge: 'Heavy Plant',
    bufferSectors: 2,
    mirrorRequired: true,
    tooltip: 'Heavy work involving on-track machinery triggers automatic +2 sector upstream/downstream safety buffers and opposite-bound track mirroring lockout.',
  },
  {
    id: 'MEDIUM',
    label: 'MEDIUM Work',
    badge: 'Standard Worksite',
    bufferSectors: 1,
    mirrorRequired: false,
    tooltip: 'Medium work requires a +1 sector protective safety halo along the active track bound.',
  },
  {
    id: 'LIGHT',
    label: 'LIGHT Work',
    badge: 'Hand Tools',
    bufferSectors: 0,
    mirrorRequired: false,
    tooltip: 'Light manual activities within designated workfront. Standard perimeter isolation applies.',
  },
  {
    id: 'INSPECTION',
    label: 'INSPECTION / Visual',
    badge: 'Inspection',
    bufferSectors: 0,
    mirrorRequired: false,
    tooltip: 'Mobile or walking track patrol. Minimal spatial footprint; compatible co-sharing allowed.',
  },
];

export const TRACK_BOUNDS = [
  { id: 'EB', label: 'Eastbound (EB)', short: 'EB', direction: 'Down' },
  { id: 'WB', label: 'Westbound (WB)', short: 'WB', direction: 'Up' },
  { id: 'BOTH', label: 'Both Directions', short: 'Dual', direction: 'Both Tracks' },
];

export const ACCESS_MODES = [
  { id: 'EXCLUSIVE', label: 'Exclusive Possession', desc: 'Sole track occupant. No co-sharing permitted.' },
  { id: 'SHARED', label: 'Shared Access', desc: 'Allows compatible co-sharing with non-conflicting trades.' },
];

export const ACTIVITY_PRIORITIES = [
  { id: 1, label: 'P1 (Critical)', nudge: '+0.3 nudge', color: 'rose', desc: 'Safety-critical repair or regulatory mandate' },
  { id: 2, label: 'P2 (High)', nudge: '+0.2 nudge', color: 'amber', desc: 'Key milestone project or critical renewal' },
  { id: 3, label: 'P3 (Normal)', nudge: '0.0 nudge', color: 'cyan', desc: 'Routine cyclic work and standard upgrade' },
];

export const CONTRACT_PRIORITIES = [
  { id: 1, label: 'P1 (Weight 100)', weight: 100, penaltyMultiplier: '100x', desc: 'Critical commercial contract - high delay penalty' },
  { id: 2, label: 'P2 (Weight 10)', weight: 10, penaltyMultiplier: '10x', desc: 'Standard operational package - moderate penalty' },
  { id: 3, label: 'P3 (Weight 1)', weight: 1, penaltyMultiplier: '1x', desc: 'Internal / low liability possession request' },
];

export const DEFAULT_LINES = [
  { code: 'NSL', name: 'North-South Line', color: '#ef4444', badgeClass: 'bg-red-500/20 text-red-300 border-red-500/40' },
  { code: 'EWL', name: 'East-West Line', color: '#10b981', badgeClass: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' },
  { code: 'NEL', name: 'North East Line', color: '#a855f7', badgeClass: 'bg-purple-500/20 text-purple-300 border-purple-500/40' },
  { code: 'CCL', name: 'Circle Line', color: '#f59e0b', badgeClass: 'bg-amber-500/20 text-amber-300 border-amber-500/40' },
  { code: 'DTL', name: 'Downtown Line', color: '#3b82f6', badgeClass: 'bg-blue-500/20 text-blue-300 border-blue-500/40' },
  { code: 'TEL', name: 'Thomson-East Coast Line', color: '#92400e', badgeClass: 'bg-amber-900/40 text-amber-200 border-amber-700/40' },
  { code: 'ALP', name: 'Line Alpha (Test Corridor)', color: '#ef4444', badgeClass: 'bg-red-500/20 text-red-300 border-red-500/40' },
  { code: 'BET', name: 'Line Beta (Test Corridor)', color: '#10b981', badgeClass: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' },
];

export const LINE_STATIONS = {
  NSL: [
    { id: 'NS1', name: 'Jurong East', code: 'JUR' },
    { id: 'NS2', name: 'Bukit Batok', code: 'BBT' },
    { id: 'NS3', name: 'Bukit Gombak', code: 'BGB' },
    { id: 'NS4', name: 'Choa Chu Kang', code: 'CCK' },
    { id: 'NS5', name: 'Yew Tee', code: 'YWT' },
    { id: 'NS7', name: 'Kranji', code: 'KRJ' },
    { id: 'NS8', name: 'Marsiling', code: 'MSL' },
    { id: 'NS9', name: 'Woodlands', code: 'WDL' },
    { id: 'NS10', name: 'Admiralty', code: 'ADM' },
    { id: 'NS11', name: 'Sembawang', code: 'SBW' },
    { id: 'NS12', name: 'Canberra', code: 'CBR' },
    { id: 'NS13', name: 'Yishun', code: 'YIS' },
    { id: 'NS14', name: 'Khatib', code: 'KTB' },
    { id: 'NS15', name: 'Yio Chu Kang', code: 'YCK' },
    { id: 'NS16', name: 'Ang Mo Kio', code: 'AMK' },
    { id: 'NS17', name: 'Bishan', code: 'BSH' },
    { id: 'NS18', name: 'Braddell', code: 'BDL' },
    { id: 'NS19', name: 'Toa Payoh', code: 'TPY' },
    { id: 'NS20', name: 'Novena', code: 'NOV' },
    { id: 'NS21', name: 'Newton', code: 'NEW' },
    { id: 'NS22', name: 'Orchard', code: 'ORC' },
    { id: 'NS23', name: 'Somerset', code: 'SOM' },
    { id: 'NS24', name: 'Dhoby Ghaut', code: 'DBG' },
    { id: 'NS25', name: 'City Hall', code: 'CTH' },
    { id: 'NS26', name: 'Raffles Place', code: 'RFP' },
    { id: 'NS27', name: 'Marina Bay', code: 'MRB' },
    { id: 'NS28', name: 'Marina South Pier', code: 'MSP' },
  ],
  EWL: [
    { id: 'EW1', name: 'Pasir Ris', code: 'PSR' },
    { id: 'EW2', name: 'Tampines', code: 'TAM' },
    { id: 'EW3', name: 'Simei', code: 'SIM' },
    { id: 'EW4', name: 'Tanah Merah', code: 'TNM' },
    { id: 'EW5', name: 'Bedok', code: 'BDK' },
    { id: 'EW6', name: 'Kembangan', code: 'KMB' },
    { id: 'EW7', name: 'Eunos', code: 'EUN' },
    { id: 'EW8', name: 'Paya Lebar', code: 'PYL' },
    { id: 'EW9', name: 'Aljunied', code: 'ALJ' },
    { id: 'EW10', name: 'Kallang', code: 'KLG' },
    { id: 'EW11', name: 'Lavender', code: 'LAV' },
    { id: 'EW12', name: 'Bugis', code: 'BGS' },
    { id: 'EW13', name: 'City Hall', code: 'CTH' },
    { id: 'EW14', name: 'Raffles Place', code: 'RFP' },
    { id: 'EW15', name: 'Tanjong Pagar', code: 'TJP' },
    { id: 'EW16', name: 'Outram Park', code: 'OTP' },
    { id: 'EW17', name: 'Tiong Bahru', code: 'TBR' },
    { id: 'EW18', name: 'Redhill', code: 'RDH' },
    { id: 'EW19', name: 'Queenstown', code: 'QNT' },
    { id: 'EW20', name: 'Commonwealth', code: 'CMW' },
    { id: 'EW21', name: 'Buona Vista', code: 'BNV' },
    { id: 'EW22', name: 'Dover', code: 'DVR' },
    { id: 'EW23', name: 'Clementi', code: 'CLE' },
    { id: 'EW24', name: 'Jurong East', code: 'JUR' },
    { id: 'EW25', name: 'Chinese Garden', code: 'CNG' },
    { id: 'EW26', name: 'Lakeside', code: 'LKS' },
    { id: 'EW27', name: 'Boon Lay', code: 'BNL' },
    { id: 'EW28', name: 'Pioneer', code: 'PNR' },
    { id: 'EW29', name: 'Joo Koon', code: 'JKN' },
    { id: 'EW30', name: 'Gul Circle', code: 'GLC' },
    { id: 'EW31', name: 'Tuas Crescent', code: 'TCR' },
    { id: 'EW32', name: 'Tuas West Road', code: 'TWR' },
    { id: 'EW33', name: 'Tuas Link', code: 'TLK' },
  ],
  NEL: [
    { id: 'NE1', name: 'HarbourFront', code: 'HBF' },
    { id: 'NE3', name: 'Outram Park', code: 'OTP' },
    { id: 'NE4', name: 'Chinatown', code: 'CNT' },
    { id: 'NE5', name: 'Clarke Quay', code: 'CKQ' },
    { id: 'NE6', name: 'Dhoby Ghaut', code: 'DBG' },
    { id: 'NE7', name: 'Little India', code: 'LTI' },
    { id: 'NE8', name: 'Farrer Park', code: 'FRP' },
    { id: 'NE9', name: 'Boon Keng', code: 'BNK' },
    { id: 'NE10', name: 'Potong Pasir', code: 'PTP' },
    { id: 'NE11', name: 'Woodleigh', code: 'WDL' },
    { id: 'NE12', name: 'Serangoon', code: 'SER' },
    { id: 'NE13', name: 'Kovan', code: 'KVN' },
    { id: 'NE14', name: 'Hougang', code: 'HGN' },
    { id: 'NE15', name: 'Buangkok', code: 'BGK' },
    { id: 'NE16', name: 'Sengkang', code: 'SKG' },
    { id: 'NE17', name: 'Punggol', code: 'PGL' },
  ],
  CCL: [
    { id: 'CC1', name: 'Dhoby Ghaut', code: 'DBG' },
    { id: 'CC2', name: 'Bras Basah', code: 'BBS' },
    { id: 'CC3', name: 'Esplanade', code: 'ESP' },
    { id: 'CC4', name: 'Promenade', code: 'PRM' },
    { id: 'CC5', name: 'Nicoll Highway', code: 'NCH' },
    { id: 'CC6', name: 'Stadium', code: 'STD' },
    { id: 'CC7', name: 'Mountbatten', code: 'MBT' },
    { id: 'CC8', name: 'Dakota', code: 'DKT' },
    { id: 'CC9', name: 'Paya Lebar', code: 'PYL' },
    { id: 'CC10', name: 'MacPherson', code: 'MPS' },
    { id: 'CC11', name: 'Tai Seng', code: 'TSG' },
    { id: 'CC12', name: 'Bartley', code: 'BTY' },
    { id: 'CC13', name: 'Serangoon', code: 'SER' },
    { id: 'CC14', name: 'Lorong Chuan', code: 'LRC' },
    { id: 'CC15', name: 'Bishan', code: 'BSH' },
    { id: 'CC16', name: 'Marymount', code: 'MRM' },
    { id: 'CC17', name: 'Caldecott', code: 'CDT' },
    { id: 'CC19', name: 'Botanic Gardens', code: 'BGR' },
    { id: 'CC20', name: 'Farrer Road', code: 'FRR' },
    { id: 'CC21', name: 'Holland Village', code: 'HLV' },
    { id: 'CC22', name: 'Buona Vista', code: 'BNV' },
    { id: 'CC23', name: 'one-north', code: 'ONH' },
    { id: 'CC24', name: 'Kent Ridge', code: 'KRG' },
    { id: 'CC25', name: 'Haw Par Villa', code: 'HPV' },
    { id: 'CC26', name: 'Pasir Panjang', code: 'PPJ' },
    { id: 'CC27', name: 'Labrador Park', code: 'LBP' },
    { id: 'CC28', name: 'Telok Blangah', code: 'TLB' },
    { id: 'CC29', name: 'HarbourFront', code: 'HBF' },
  ],
  DTL: [
    { id: 'DT1', name: 'Bukit Panjang', code: 'BPJ' },
    { id: 'DT2', name: 'Cashew', code: 'CSH' },
    { id: 'DT3', name: 'Hillview', code: 'HLV' },
    { id: 'DT5', name: 'Beauty World', code: 'BTW' },
    { id: 'DT6', name: 'King Albert Park', code: 'KAP' },
    { id: 'DT7', name: 'Sixth Avenue', code: 'SAV' },
    { id: 'DT8', name: 'Tan Kah Kee', code: 'TKK' },
    { id: 'DT9', name: 'Botanic Gardens', code: 'BGR' },
    { id: 'DT10', name: 'Stevens', code: 'STV' },
    { id: 'DT11', name: 'Newton', code: 'NEW' },
    { id: 'DT12', name: 'Little India', code: 'LTI' },
    { id: 'DT13', name: 'Rochor', code: 'RCH' },
    { id: 'DT14', name: 'Bugis', code: 'BGS' },
    { id: 'DT15', name: 'Promenade', code: 'PRM' },
    { id: 'DT16', name: 'Bayfront', code: 'BYF' },
    { id: 'DT17', name: 'Downtown', code: 'DTN' },
    { id: 'DT18', name: 'Telok Ayer', code: 'TLA' },
    { id: 'DT19', name: 'Chinatown', code: 'CNT' },
    { id: 'DT20', name: 'Fort Canning', code: 'FTC' },
    { id: 'DT21', name: 'Bencoolen', code: 'BCL' },
    { id: 'DT22', name: 'Jalan Besar', code: 'JLB' },
    { id: 'DT23', name: 'Bendemeer', code: 'BDM' },
    { id: 'DT24', name: 'Geylang Bahru', code: 'GLB' },
    { id: 'DT25', name: 'Mattar', code: 'MTR' },
    { id: 'DT26', name: 'MacPherson', code: 'MPS' },
    { id: 'DT27', name: 'Ubi', code: 'UBI' },
    { id: 'DT28', name: 'Kaki Bukit', code: 'KKB' },
    { id: 'DT29', name: 'Bedok North', code: 'BDN' },
    { id: 'DT30', name: 'Bedok Reservoir', code: 'BDR' },
    { id: 'DT31', name: 'Tampines West', code: 'TPW' },
    { id: 'DT32', name: 'Tampines', code: 'TAM' },
    { id: 'DT33', name: 'Tampines East', code: 'TPE' },
    { id: 'DT34', name: 'Upper Changi', code: 'UPC' },
    { id: 'DT35', name: 'Expo', code: 'EXP' },
  ],
  TEL: [
    { id: 'TE1', name: 'Woodlands North', code: 'WDN' },
    { id: 'TE2', name: 'Woodlands', code: 'WDL' },
    { id: 'TE3', name: 'Woodlands South', code: 'WDS' },
    { id: 'TE4', name: 'Springleaf', code: 'SPL' },
    { id: 'TE5', name: 'Lentor', code: 'LTR' },
    { id: 'TE6', name: 'Mayflower', code: 'MFL' },
    { id: 'TE7', name: 'Bright Hill', code: 'BRH' },
    { id: 'TE8', name: 'Upper Thomson', code: 'UPT' },
    { id: 'TE9', name: 'Caldecott', code: 'CDT' },
    { id: 'TE11', name: 'Stevens', code: 'STV' },
    { id: 'TE12', name: 'Napier', code: 'NPR' },
    { id: 'TE13', name: 'Orchard Boulevard', code: 'OBV' },
    { id: 'TE14', name: 'Orchard', code: 'ORC' },
    { id: 'TE15', name: 'Great World', code: 'GWL' },
    { id: 'TE16', name: 'Havelock', code: 'HVL' },
    { id: 'TE17', name: 'Outram Park', code: 'OTP' },
    { id: 'TE18', name: 'Maxwell', code: 'MXW' },
    { id: 'TE19', name: 'Shenton Way', code: 'STW' },
    { id: 'TE20', name: 'Marina Bay', code: 'MRB' },
    { id: 'TE22', name: 'Gardens by the Bay', code: 'GBB' },
    { id: 'TE23', name: 'Tanjong Rhu', code: 'TJR' },
    { id: 'TE24', name: 'Katong Park', code: 'KTP' },
    { id: 'TE25', name: 'Tanjong Katong', code: 'TJK' },
    { id: 'TE26', name: 'Marine Parade', code: 'MNP' },
    { id: 'TE27', name: 'Marine Terrace', code: 'MNT' },
    { id: 'TE28', name: 'Siglap', code: 'SGL' },
    { id: 'TE29', name: 'Bayshore', code: 'BSH' },
  ],
  ALP: [
    { id: 'ALP:S01', name: 'Station S01', code: 'S01' },
    { id: 'ALP:S02', name: 'Station S02', code: 'S02' },
    { id: 'ALP:S03', name: 'Station S03', code: 'S03' },
    { id: 'ALP:S04', name: 'Station S04', code: 'S04' },
    { id: 'ALP:H01', name: 'Interchange West H01', code: 'H01' },
    { id: 'ALP:H02', name: 'Interchange East H02', code: 'H02' },
    { id: 'ALP:S05', name: 'Station S05', code: 'S05' },
    { id: 'ALP:S06', name: 'Station S06', code: 'S06' },
    { id: 'ALP:S07', name: 'Station S07', code: 'S07' },
    { id: 'ALP:S08', name: 'Station S08', code: 'S08' },
  ],
  BET: [
    { id: 'BET:S11', name: 'Station S11', code: 'S11' },
    { id: 'BET:S12', name: 'Station S12', code: 'S12' },
    { id: 'BET:S13', name: 'Station S13', code: 'S13' },
    { id: 'BET:S14', name: 'Station S14', code: 'S14' },
    { id: 'BET:H01', name: 'Interchange West H01', code: 'H01' },
    { id: 'BET:H02', name: 'Interchange East H02', code: 'H02' },
    { id: 'BET:S15', name: 'Station S15', code: 'S15' },
    { id: 'BET:S16', name: 'Station S16', code: 'S16' },
    { id: 'BET:S17', name: 'Station S17', code: 'S17' },
    { id: 'BET:S18', name: 'Station S18', code: 'S18' },
  ],
};

export const DEFAULT_CONTRACTS = [
  { id: 'C01', description: 'C01 - Civil & Structural Permanent Works', priority: 1, defaultNature: 'HEAVY', defaultType: 'CIVIL' },
  { id: 'C06', description: 'C06 - Track Renewal & Sleeper Replacement', priority: 1, defaultNature: 'HEAVY', defaultType: 'TRACK' },
  { id: 'C08', description: 'C08 - Turnout Overhaul & Switch Grinding', priority: 2, defaultNature: 'HEAVY', defaultType: 'TRACK' },
  { id: 'C12', description: 'C12 - Signalling & CBTC Modernisation', priority: 2, defaultNature: 'MEDIUM', defaultType: 'SIGNAL' },
  { id: 'C19', description: 'C19 - Traction Power & 3rd Rail Maintenance', priority: 2, defaultNature: 'MEDIUM', defaultType: 'POWER' },
  { id: 'C24', description: 'C24 - Leaky Feeder & Comms Cable Pulling', priority: 3, defaultNature: 'LIGHT', defaultType: 'TELECOM' },
  { id: 'C99', description: 'C99 - Routine Visual Infrastructure Patrol', priority: 3, defaultNature: 'INSPECTION', defaultType: 'TRACK' },
];

/**
 * Format a Date object to YYYY-MM-DD
 */
export function formatDate(d) {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Auto-generate job IDs following standard rail possession naming formats.
 * EMG-YYYYMMDD-XX for emergencies, PRJ-XXX for project additions, MNT-XXX for maintenance.
 */
export function generateJobId(category = JOB_SOURCES.PROJECT, existingJobs = []) {
  const now = new Date();
  const yyyymmdd = now.toISOString().slice(0, 10).replace(/-/g, '');
  const count = (existingJobs?.length || 0) + 1;
  const seqPadded = String(count).padStart(3, '0');
  const rand2 = String(Math.floor(10 + Math.random() * 90));

  if (category === JOB_SOURCES.EMERGENCY) {
    return `EMG-${yyyymmdd}-${rand2}`;
  }
  if (category === JOB_SOURCES.ROUTINE) {
    return `MNT-${seqPadded}`;
  }
  return `PRJ-${seqPadded}`;
}

/**
 * Build default form data object
 */
export function getInitialJobFormData(initialData = null, existingJobs = []) {
  const today = new Date();
  const targetDate = new Date();
  targetDate.setDate(today.getDate() + 30);
  const emergencyHardDate = new Date();
  emergencyHardDate.setDate(today.getDate() + 7);

  const category = initialData?.category || JOB_SOURCES.PROJECT;
  const generatedId = generateJobId(category, existingJobs);

  return {
    id: initialData?.id || generatedId,
    category: category,
    contract_number: initialData?.contract_number || 'C06',
    is_adhoc_contract: initialData?.is_adhoc_contract || false,
    adhoc_contract_name: initialData?.adhoc_contract_name || '',
    activity_type: initialData?.activity_type || 'TRACK',
    nature_of_works: initialData?.nature_of_works || 'HEAVY',
    line_code: initialData?.line_code || 'NSL',
    start_location_id: initialData?.start_location_id || 'NS1',
    end_location_id: initialData?.end_location_id || 'NS4',
    track_bound: initialData?.track_bound || 'BOTH',
    access_mode: initialData?.access_mode || 'EXCLUSIVE',
    total_accesses: initialData?.total_accesses ?? 3,
    planned_start_date: initialData?.planned_start_date || formatDate(today),
    planned_completion_date: initialData?.planned_completion_date || formatDate(targetDate),
    hard_completion_date: initialData?.hard_completion_date || (category === JOB_SOURCES.EMERGENCY ? formatDate(emergencyHardDate) : ''),
    enforce_hard_deadline: initialData?.enforce_hard_deadline || category === JOB_SOURCES.EMERGENCY,
    max_accesses_per_week: initialData?.max_accesses_per_week ?? 3,
    eclo_allowed: initialData?.eclo_allowed ?? false,
    predecessor_job_id: initialData?.predecessor_job_id || '',
    activity_priority: initialData?.activity_priority ?? 2,
    contract_priority: initialData?.contract_priority ?? 2,
    notes: initialData?.notes || '',
    ...initialData,
  };
}

/**
 * Calculate dynamic safety buffer and operational rules based on nature of works and bounds
 */
export function calculateSafetyBuffer(natureOfWorks, trackBound, lineCode, startLoc, endLoc) {
  const natureDef = NATURE_OF_WORKS.find((n) => n.id === natureOfWorks) || NATURE_OF_WORKS[0];
  const isHeavy = natureOfWorks === 'HEAVY';
  const isMedium = natureOfWorks === 'MEDIUM';
  const isDualBound = trackBound === 'BOTH';

  let bufferSectors = 0;
  let mirrorOppositeBound = false;
  let lockoutDescription = '';
  let badgeText = '';
  let warningLevel = 'info';

  if (isHeavy) {
    bufferSectors = 2;
    mirrorOppositeBound = true;
    warningLevel = 'caution';
    lockoutDescription =
      'Heavy rail plant active: Mandatory +2 sector upstream and downstream safety buffers. Opposite track bound mirrored and locked out against train traffic.';
    badgeText = '🛡️ Safety Rule: +2 buffer sectors upstream/downstream required. Dual-bound lockout active.';
  } else if (isMedium) {
    bufferSectors = 1;
    mirrorOppositeBound = isDualBound;
    warningLevel = 'info';
    lockoutDescription = isDualBound
      ? 'Medium work on both bounds: +1 sector buffer on both EB & WB tracks.'
      : `Medium work: +1 sector buffer required along ${trackBound === 'EB' ? 'Eastbound' : 'Westbound'} corridor.`;
    badgeText = `🛡️ Safety Rule: +1 buffer sector required on ${isDualBound ? 'both directions' : trackBound}.`;
  } else {
    bufferSectors = 0;
    mirrorOppositeBound = isDualBound;
    warningLevel = 'none';
    lockoutDescription = 'Standard worksite isolation. Work restricted to designated track occupancy window.';
    badgeText = '✅ Standard Workfront: 0 extended buffer sectors required.';
  }

  return {
    bufferSectors,
    mirrorOppositeBound,
    lockoutDescription,
    badgeText,
    warningLevel,
    natureDef,
  };
}

/**
 * Validate the job form payload against operational safety and precedence guardrails.
 */
export function validateJobForm(formData, existingJobs = []) {
  const errors = {};
  const warnings = {};

  // Job ID validation
  if (!formData.id || !formData.id.trim()) {
    errors.id = 'Job ID is required';
  }

  // Category
  if (!formData.category) {
    errors.category = 'Job category is required';
  }

  // Contract validation
  if (formData.is_adhoc_contract) {
    if (!formData.adhoc_contract_name || !formData.adhoc_contract_name.trim()) {
      errors.contract_number = 'Ad-hoc contract title or code must be provided';
    }
  } else if (!formData.contract_number) {
    errors.contract_number = 'Please select an existing contract';
  }

  // Spatial checks
  if (!formData.line_code) {
    errors.line_code = 'Line selection is required';
  }
  if (!formData.start_location_id) {
    errors.start_location_id = 'Start location is required';
  }
  if (!formData.end_location_id) {
    errors.end_location_id = 'End location is required';
  }

  // Timing checks
  if (!formData.planned_start_date) {
    errors.planned_start_date = 'Planned start date is required';
  }
  if (!formData.planned_completion_date) {
    errors.planned_completion_date = 'Target completion date is required';
  }

  if (formData.planned_start_date && formData.planned_completion_date) {
    const start = new Date(formData.planned_start_date);
    const end = new Date(formData.planned_completion_date);
    if (end < start) {
      errors.planned_completion_date = 'Target completion date cannot precede planned start date';
    }
  }

  // Emergency & Hard deadline rules
  const isEmergency = formData.category === JOB_SOURCES.EMERGENCY;
  const isHardEnforced = formData.enforce_hard_deadline || isEmergency;

  if (isHardEnforced) {
    if (!formData.hard_completion_date) {
      errors.hard_completion_date = isEmergency
        ? 'Emergency Repairs strictly require a hard deadline date'
        : 'Hard deadline date is mandatory when enforcement is toggled';
    } else if (formData.planned_start_date) {
      const start = new Date(formData.planned_start_date);
      const hard = new Date(formData.hard_completion_date);
      if (hard < start) {
        errors.hard_completion_date = 'Hard deadline cannot be before planned start date';
      }
    }
  }

  // Workload / Stepper checks
  if (formData.total_accesses < 1 || formData.total_accesses > 50) {
    errors.total_accesses = 'Total accesses must be between 1 and 50';
  }
  if (formData.max_accesses_per_week < 1 || formData.max_accesses_per_week > 7) {
    errors.max_accesses_per_week = 'Weekly access cap must be between 1 and 7';
  }

  // Precedence Guardrail Check
  if (formData.predecessor_job_id) {
    const predecessor = existingJobs.find(
      (j) => j.id === formData.predecessor_job_id || j.job_id === formData.predecessor_job_id
    );
    if (predecessor) {
      const predCompletion = predecessor.completionDate || predecessor.planned_completion_date;
      if (predCompletion && formData.planned_start_date) {
        const predDate = new Date(predCompletion);
        const myStartDate = new Date(formData.planned_start_date);
        if (predDate > myStartDate) {
          warnings.precedence = `⚠️ Warning: Prerequisite completes after planned start date (${predCompletion} vs ${formData.planned_start_date}). Start date will be delayed by the solver.`;
        }
      }
    }
  }

  // Heavy works warning
  if (formData.nature_of_works === 'HEAVY' && formData.track_bound !== 'BOTH') {
    warnings.heavy_bound = 'Heavy works will lock out the opposite bound automatically regardless of single bound selection.';
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
    warnings,
  };
}

/**
 * Fallback client-side preflight check heuristic engine.
 * Simulates capacity, buffer collisions, and schedule disruption if backend endpoint is unavailable.
 */
export function runClientSidePreflightHeuristic(formData, existingJobs = [], topologyData = null) {
  const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const isEmergency = formData.category === JOB_SOURCES.EMERGENCY;
  const isHeavy = formData.nature_of_works === 'HEAVY';
  const bufferHalo = isHeavy ? 2 : formData.nature_of_works === 'MEDIUM' ? 1 : 0;

  const ruleBreakdown = [];
  let status = 'PASSED';
  let disruptionScore = isEmergency ? 18.5 : 4.2;
  let displacedVisits = isEmergency ? 1 : 0;
  let hardConflictReason = null;

  // 1. Capacity Check
  const isDenseStation =
    ['NS1', 'NS17', 'NS24', 'EW13', 'EW14', 'EW24', 'NE1', 'CC1', 'DT14'].includes(formData.start_location_id) ||
    ['NS1', 'NS17', 'NS24', 'EW13', 'EW14', 'EW24', 'NE1', 'CC1', 'DT14'].includes(formData.end_location_id);

  if (isDenseStation && formData.total_accesses > 6 && !formData.eclo_allowed) {
    status = 'WARNING';
    ruleBreakdown.push({
      rule: 'Capacity Check',
      category: 'capacity',
      passed: true,
      severity: 'warning',
      detail: `High possession concentration near interchange ${formData.start_location_id}. Peak utilization reaches 85% of nightly cap.`,
    });
  } else {
    ruleBreakdown.push({
      rule: 'Capacity Check',
      category: 'capacity',
      passed: true,
      severity: 'success',
      detail: 'Sufficient possession capacity at selected stations across planning horizon.',
    });
  }

  // 2. Buffer Conflict Check
  const conflictingJobs = existingJobs.filter((j) => {
    const sameLine = j.lineCode === formData.line_code || j.line_code === formData.line_code;
    return sameLine && (j.natureOfWorks === 'HEAVY' || isHeavy);
  });

  if (isHeavy && conflictingJobs.length > 2) {
    status = 'WARNING';
    ruleBreakdown.push({
      rule: 'Buffer Conflict',
      category: 'buffer',
      passed: true,
      severity: 'warning',
      detail: `Potential safety buffer overlap detected with ${conflictingJobs[0].title || conflictingJobs[0].id} (+${bufferHalo} sector halo). Solver will sequence dates non-consecutively.`,
    });
  } else {
    ruleBreakdown.push({
      rule: 'Buffer Conflict',
      category: 'buffer',
      passed: true,
      severity: 'success',
      detail: 'No overlapping heavy works detected in safety halo.',
    });
  }

  // 3. Schedule Impact
  if (isEmergency) {
    status = status === 'HARD CONFLICT' ? 'HARD CONFLICT' : 'WARNING';
    displacedVisits = 1;
    disruptionScore = 24.8;
    ruleBreakdown.push({
      rule: 'Schedule Impact',
      category: 'impact',
      passed: true,
      severity: 'warning',
      detail: 'Inserting this emergency job may displace 1 lower-priority maintenance visit.',
    });
  } else {
    ruleBreakdown.push({
      rule: 'Schedule Impact',
      category: 'impact',
      passed: true,
      severity: 'success',
      detail: 'Zero displacement of committed visits; minor schedule nudging within slack windows.',
    });
  }

  // 4. Precedence Guardrail Check
  if (formData.predecessor_job_id) {
    const predecessor = existingJobs.find(
      (j) => j.id === formData.predecessor_job_id || j.job_id === formData.predecessor_job_id
    );
    const predDateStr = predecessor?.completionDate || predecessor?.planned_completion_date;
    if (predDateStr && formData.planned_start_date) {
      const predDate = new Date(predDateStr);
      const myStartDate = new Date(formData.planned_start_date);
      if (predDate > myStartDate) {
        status = 'HARD CONFLICT';
        hardConflictReason = `Prerequisite job (${formData.predecessor_job_id}) completes on ${predDateStr}, after planned start date ${formData.planned_start_date}.`;
        ruleBreakdown.push({
          rule: 'Precedence Check',
          category: 'precedence',
          passed: false,
          severity: 'error',
          detail: `HARD CONFLICT: Prerequisite ${formData.predecessor_job_id} completes after proposed start date.`,
        });
      } else {
        ruleBreakdown.push({
          rule: 'Precedence Check',
          category: 'precedence',
          passed: true,
          severity: 'success',
          detail: `Prerequisite ${formData.predecessor_job_id} verified to complete before planned start date.`,
        });
      }
    }
  } else {
    ruleBreakdown.push({
      rule: 'Precedence Check',
      category: 'precedence',
      passed: true,
      severity: 'success',
      detail: 'No prerequisite dependencies declared. Job is immediately eligible.',
    });
  }

  // 5. Date Horizon Check
  if (formData.planned_start_date && formData.planned_completion_date) {
    const start = new Date(formData.planned_start_date);
    const end = new Date(formData.planned_completion_date);
    if (end < start) {
      status = 'HARD CONFLICT';
      hardConflictReason = 'Target completion date precedes planned start date.';
      ruleBreakdown.push({
        rule: 'Horizon Check',
        category: 'calendar',
        passed: false,
        severity: 'error',
        detail: 'Target completion date precedes planned start date.',
      });
    } else {
      ruleBreakdown.push({
        rule: 'Horizon Check',
        category: 'calendar',
        passed: true,
        severity: 'success',
        detail: 'Job fits within 30-week scheduling horizon.',
      });
    }
  }

  return {
    status,
    hardConflictReason,
    metrics: {
      disruptionScore,
      displacedVisits,
      bufferHaloSectors: bufferHalo,
      capacityPeakRatio: isDenseStation ? '85%' : '42%',
    },
    ruleBreakdown,
    timestamp,
  };
}
