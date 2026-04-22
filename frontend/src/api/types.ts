// ---------------------------------------------------------------------------
// API types — mirror of backend Pydantic schemas (backend/app/schemas/)
// ---------------------------------------------------------------------------

export interface IngredientVariant {
  rivm_item_id: number;
  label: string;
  stage: string;
  prep_method: string | null;
  packaging: string | null;
  conditions: string | null;
  co2_kgco2eq: number | null;
  so2_kg: number | null;
  p_kg: number | null;
  n_kg: number | null;
  land_m2a: number | null;
  water_m3: number | null;
}

export interface IngredientGroup {
  primary_name: string;
  nevo_code: number | null;
  nevo_name_nl: string | null;
  nevo_name_en: string | null;
  nevo_productgroup_nl: string | null;
  nevo_productgroup_en: string | null;
  score: number;
  variants: IngredientVariant[];
}

export interface IngredientSearchResponse {
  mode: string;
  query: string;
  results: IngredientGroup[];
}

export interface NevoNutritionOut {
  nevo_code: number;
  dutch_name: string | null;
  english_name: string | null;
  synonym: string | null;
  food_group_nl: string | null;
  food_group_en: string | null;
  quantity: string | null;
  kj: number | null;
  kcal: number | null;
  water_g: number | null;
  protein_g: number | null;
  protein_plant_g: number | null;
  protein_animal_g: number | null;
  fat_g: number | null;
  fat_saturated_g: number | null;
  fat_mono_g: number | null;
  fat_poly_g: number | null;
  carb_g: number | null;
  sugar_g: number | null;
  starch_g: number | null;
  fibre_g: number | null;
  alcohol_g: number | null;
  sodium_mg: number | null;
  calcium_mg: number | null;
  iron_mg: number | null;
  vitamin_c_mg: number | null;
  vitamin_d_ug: number | null;
  raw_nutrients: Record<string, unknown> | null;
}

export interface RivmItemDetail {
  id: number;
  stage: string;
  nevo_code: number | null;
  primary_name: string;
  prep_method: string | null;
  packaging: string | null;
  conditions: string | null;
  raw_name: string;
  nevo_naam_nl: string | null;
  nevo_name_en: string | null;
  nevo_productgroup_nl: string | null;
  nevo_productgroup_en: string | null;
  co2_kgco2eq: number | null;
  so2_kg: number | null;
  p_kg: number | null;
  n_kg: number | null;
  land_m2a: number | null;
  water_m3: number | null;
  nutrition: NevoNutritionOut | null;
}

// ---------------------------------------------------------------------------
// Auth types
// ---------------------------------------------------------------------------

export interface UserOut {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
}

// ---------------------------------------------------------------------------
// Meal persistence types
// ---------------------------------------------------------------------------

export interface MealIngredientIn {
  rivm_item_id: number;
  primary_name: string;
  amount: number;
  unit: Unit;
  position: number;
}

export interface MealIn {
  name: string;
  notes?: string;
  ingredients: MealIngredientIn[];
}

export interface MealIngredientOut {
  id: string;
  rivm_item_id: number;
  primary_name: string;
  amount: number;
  unit: Unit;
  position: number;
}

export interface MealOut {
  id: string;
  name: string;
  notes: string;
  created_at: string;
  ingredients: MealIngredientOut[];
}

export interface MealListItem {
  id: string;
  name: string;
  notes: string;
  created_at: string;
  ingredient_count: number;
}

// ---------------------------------------------------------------------------
// Local meal state
// ---------------------------------------------------------------------------

export type Unit = 'g' | 'kg' | 'ml' | 'L' | 'piece';

export interface MealItem {
  /** Stable React key — local UUID, never sent to server */
  uid: string;
  rivm_item_id: number;
  primary_name: string;
  /** Currently selected variant (environmental impact data) */
  variant: IngredientVariant;
  /** All variants for this ingredient group (for the picker) */
  all_variants: IngredientVariant[];
  amount: number;
  unit: Unit;
  /** Nutrition per 100 g — fetched once on add, stays constant across variant changes */
  nutrition: NevoNutritionOut | null;
}

// ---------------------------------------------------------------------------
// Procurement persistence types
// ---------------------------------------------------------------------------

export interface ProcurementItemIn {
  rivm_item_id: number;
  primary_name: string;
  amount: number;
  unit: Unit;
  position: number;
}

export interface ProcurementIn {
  name: string;
  notes?: string;
  items: ProcurementItemIn[];
}

export interface ProcurementItemOut {
  id: string;
  rivm_item_id: number;
  primary_name: string;
  amount: number;
  unit: Unit;
  position: number;
}

export interface ProcurementOut {
  id: string;
  name: string;
  notes: string;
  created_at: string;
  items: ProcurementItemOut[];
}

export interface ProcurementListItem {
  id: string;
  name: string;
  notes: string;
  created_at: string;
  item_count: number;
}

/** The 6 RIVM environmental metric keys */
export type MetricKey =
  | 'co2_kgco2eq'
  | 'so2_kg'
  | 'p_kg'
  | 'n_kg'
  | 'land_m2a'
  | 'water_m3';
