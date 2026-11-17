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
      'The only runnable modality. The fictional workflow and experimental evaluations are not clinically or psychometrically validated.',
    status: 'available',
    version: '0.2',
  },
]

export const plannedTherapyCategories = [
  'categoryCognitive',
  'categoryMindfulness',
  'categoryCompassion',
  'categorySystemic',
] as const