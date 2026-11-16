import type { TherapyModule } from '../types'

/*
 * The registry is intentionally independent from the interface.
 * New therapy approaches can be added without rewriting navigation.
 *
 * A listed approach is not necessarily an operational treatment module.
 */

export const therapyModules: TherapyModule[] = [
  {
    id: 'act',
    code: 'ACT',
    name: 'Acceptance and Commitment Therapy',
    description:
      'Initial project approach. Its simulation scenarios, session contracts and versioned evaluation rubrics are under development.',
    status: 'designing',
    version: '0.1',
  },
]

export const plannedTherapyCategories = [
  'categoryCognitive',
  'categoryMindfulness',
  'categoryCompassion',
  'categorySystemic',
] as const