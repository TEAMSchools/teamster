SELECT
  ar.contact_id,
  ar.contact_full_name AS student_name,
  ar.ktc_cohort AS hs_cohort,
  ar.ktc_status AS status,
  ar.contact_currently_enrolled_school AS currently_enrolled_school,
  ar.contact_owner_name,
  enr.ugrad_account_type,
  enr.ugrad_account_name,
  enr.ugrad_date_last_verified,
  enr.ugrad_anticipated_graduation,
  enr.ugrad_status,
  t.Term_Season__c AS semester,
  LEFT(t.Year__c, 4) AS year,
  CONCAT(UPPER(LEFT(t.Term_Season__c, 2)), ' ', RIGHT(LEFT(t.Year__c, 4), 2)) AS term,
  CASE
    WHEN t.Verified_by_Advisor__c IS NOT NULL THEN 'Verified by Counselor'
    WHEN t.Verified_by_NSC__c IS NOT NULL THEN 'Verified by NSC'
  ELSE
  'Unverified'
END
  AS verification_status,
  t.Term_Verification_Status__c AS verification_status_src,
  COALESCE(t.Verified_by_Advisor__c, t.Verified_by_NSC__c) AS verification_date,
  ROW_NUMBER() OVER(PARTITION BY ar.contact_id, t.Term_Season__c, t.Year__c ORDER BY t.Term_Verification_Status__c DESC) AS rn_term
FROM
  {{ ref('int_kippadb__roster') }} AS ar
INNER JOIN
  {{ ref('int_kippadb__enrollment_pivot') }} AS enr
ON
  (ar.contact_id = enr.student
    AND enr.ugrad_account_name IS NOT NULL
    AND enr.ugrad_status != 'Matriculated')
INNER JOIN
  `kipptaf_kippadb.Term__c` AS t
ON
  (enr.ugrad_enrollment_id = t.Enrollment__c
    AND t.Term_Season__c != 'Summer')