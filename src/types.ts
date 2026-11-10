export interface RetirementLink {
  title: string;
  url: string;
}

interface QuestionAnswer {
  question: string;
  introduction: string;
}

export interface ChangeQuestion extends QuestionAnswer {
  announcement: string;
  financialConsiderations: string;
}

export interface ActionsQuestion extends QuestionAnswer {
  recommendedAction: string | null;
  guidance: string;
  resources: RetirementLink[];
  supportGuidance: string;
  support: RetirementLink;
}

export interface ImpactQuestion extends QuestionAnswer {
  guidance: string;
  checklist: string[];
  notice: string;
  advisor: RetirementLink;
}

export interface DeadlineQuestion extends QuestionAnswer {
  date: string | null;
  month: string | null;
  dateGuidance: string;
  consequences: string;
}

export interface ProgressQuestion extends QuestionAnswer {
  guidance: string;
  checklist: string[];
  storageNote: string;
}

export interface RetirementQuestions {
  what: ChangeQuestion;
  actions: ActionsQuestion;
  impact: ImpactQuestion;
  deadline: DeadlineQuestion;
  progress: ProgressQuestion;
}

export interface RetirementRecord {
  id: string;
  title: string;
  services: string[];
  categories?: string[];
  service: string;
  announcedOn: string | null;
  lastUpdatedOn: string | null;
  manuallyEnriched: boolean;
  summary: string;
  questions: RetirementQuestions;
  sourceUrl: string;
}

export interface RetirementCatalog {
  schemaVersion: 2;
  source: string;
  retrievedAt: string;
  records: RetirementRecord[];
}

export type RetirementStatus = 'upcoming' | 'soon' | 'retired' | 'unknown';
export type StatusFilter = 'all' | RetirementStatus;
export type SortOrder = 'date' | 'newest' | 'title';

export interface CatalogFilters {
  q: string;
  service: string;
  year: string;
  category: string;
  status: StatusFilter;
  sort: SortOrder;
}
