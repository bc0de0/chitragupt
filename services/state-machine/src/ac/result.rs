use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum AcStatus {
    Met,
    Unmet,
    Waived,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AcCriterion {
    pub id: String,
    pub description: String,
    pub status: AcStatus,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AcGap {
    pub criterion_id: String,
    pub description: String,
    pub suggested_question: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AcResult {
    pub criteria: Vec<AcCriterion>,
    pub gaps: Vec<AcGap>,
    pub transition_ready: bool,
}

impl AcResult {
    /// Build an AcResult by evaluating each criterion against session state.
    ///
    /// `checks` — `(id, description, question, field_met)` tuples:
    ///   - `field_met` is the result of a direct state field check.
    ///   - A criterion whose id is already in `ac_met` is always Met regardless of `field_met`.
    ///   - A criterion whose id is in `ac_waived` (and not in `ac_met`) is Waived.
    ///
    /// `transition_ready` is true when every non-optional criterion is Met or Waived.
    /// Optional criteria have IDs containing "-U" (upload/optional checkpoints).
    pub fn from_checks(
        checks: Vec<(&str, &str, &str, bool)>,
        ac_met: &[String],
        ac_waived: &[String],
    ) -> Self {
        let mut criteria = Vec::new();
        let mut gaps = Vec::new();

        for (id, desc, question, field_met) in checks {
            let explicitly_met = ac_met.iter().any(|m| m == id);
            let waived = ac_waived.iter().any(|w| w == id);

            let status = if explicitly_met || field_met {
                AcStatus::Met
            } else if waived {
                AcStatus::Waived
            } else {
                AcStatus::Unmet
            };

            // Surface gaps for all unmet criteria (including optional -U ones).
            // Optional criteria don't block transition but their suggested questions are still useful.
            if status == AcStatus::Unmet {
                gaps.push(AcGap {
                    criterion_id: id.to_string(),
                    description: desc.to_string(),
                    suggested_question: question.to_string(),
                });
            }

            criteria.push(AcCriterion {
                id: id.to_string(),
                description: desc.to_string(),
                status,
            });
        }

        // Optional (-U) criteria never block transition.
        let transition_ready = criteria.iter().all(|c| {
            c.id.contains("-U") || c.status == AcStatus::Met || c.status == AcStatus::Waived
        });

        AcResult {
            criteria,
            gaps,
            transition_ready,
        }
    }

    /// Convenience constructor: mark all criteria as unmet (used in tests and stubs).
    pub fn all_unmet(criteria: Vec<(&str, &str, &str)>) -> Self {
        let gaps: Vec<AcGap> = criteria
            .iter()
            .map(|(id, desc, question)| AcGap {
                criterion_id: id.to_string(),
                description: desc.to_string(),
                suggested_question: question.to_string(),
            })
            .collect();

        let criteria: Vec<AcCriterion> = criteria
            .into_iter()
            .map(|(id, desc, _)| AcCriterion {
                id: id.to_string(),
                description: desc.to_string(),
                status: AcStatus::Unmet,
            })
            .collect();

        AcResult {
            criteria,
            gaps,
            transition_ready: false,
        }
    }

    pub fn met_count(&self) -> usize {
        self.criteria
            .iter()
            .filter(|c| c.status == AcStatus::Met)
            .count()
    }

    pub fn unmet_count(&self) -> usize {
        self.criteria
            .iter()
            .filter(|c| c.status == AcStatus::Unmet)
            .count()
    }
}
