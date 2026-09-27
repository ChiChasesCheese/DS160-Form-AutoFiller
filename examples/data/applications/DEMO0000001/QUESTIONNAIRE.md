# Questionnaire — DEMO0000001

Answer any way you like; the agent persists each answer with its source:

1. **Reply in chat** — e.g. `Q1: ZHANG WEI, 1970-03-12, No`
2. **Drop a document** into `raw/inbox/` (户口本, birth certificate, old passport, …) and say so
3. **CLI** — `backhome answer <path> <value>`

`missing` = the form cannot proceed without it. `confirm` = the agent filled a default; say *ok* or correct it.

### Q1 · Petition Receipt Number

- key: `app.petition_receipt` · pages: Travel, TemporaryWork · kind: **missing**
  - Petition Receipt Number: ?
  - Application Receipt/Petition Number: ?
- answer: 

### Q2 · Have you made specific travel plans?

- key: `app.specific_travel_plans_ind` · pages: Travel · kind: **missing**
- answer: 

### Q3 · Intended Date of Arrival

- key: `app.intended_arrival` · pages: Travel · kind: **missing**
- answer: 

### Q4 · Intended Length of Stay

- key: `app.length_of_stay.value` · pages: Travel · kind: **missing**
- answer: 

### Q5 · Length of Stay unit

- key: `app.length_of_stay.unit` · pages: Travel · kind: **missing**
- answer: 

### Q6 · US stay address line 1

- key: `app.us_address.line1` · pages: Travel · kind: **missing**
- answer: 

### Q7 · City

- key: `app.us_address.city` · pages: Travel · kind: **missing**
- answer: 

### Q8 · State

- key: `app.us_address.state` · pages: Travel · kind: **missing**
- answer: 

### Q9 · ZIP Code

- key: `app.us_address.zip` · pages: Travel · kind: **missing**
- answer: 

### Q10 · Person/Entity Paying for Your Trip

- key: `app.payer` · pages: Travel · kind: **missing**
- answer: 

### Q11 · Are there other persons traveling with you?

- key: `app.travel_companions_ind` · pages: TravelCompanions · kind: **missing**
- answer: 

### Q12 · Have you ever been in the U.S.?

- key: `us_immigration.ever_in_us_ind` · pages: PreviousUSTravel · kind: **missing**
- answer: 

### Q13 · 最近 5 次入境美国的日期和停留时长（I-94 travel history 截图/PDF 放进 raw/inbox/ 最好）

- key: `us_immigration.ds160_last_visits` · pages: PreviousUSTravel · kind: **missing**
- answer: 

### Q14 · Have you ever been issued a U.S. Visa?

- key: `us_immigration.ever_issued_visa_ind` · pages: PreviousUSTravel · kind: **missing**
- answer: 

### Q15 · 签证/入境历史（全部“否”就回 No）：美国签证丢失/被盗？被取消/吊销？被拒签/入境被拒/撤回入境申请？有人替你提交过移民申请（I-130/I-140，H-1B 不算）？护照丢失/被盗过？

- key: `declarations.history` · pages: PreviousUSTravel, PptVisa · kind: **missing**
  - Ever refused a U.S. visa / refused admission / withdrew application at port of entry?: ?
  - Has anyone ever filed an immigrant petition on your behalf?: ?
  - Have you ever lost a passport or had one stolen?: N
- answer: 

### Q16 · Home Street Address (Line 1)

- key: `contact.home.line1` · pages: AddressPhone · kind: **missing**
- answer: 

### Q17 · City

- key: `contact.home.city` · pages: AddressPhone · kind: **missing**
- answer: 

### Q18 · State/Province

- key: `contact.home.state_name` · pages: AddressPhone · kind: **missing**
- answer: 

### Q19 · Postal Zone/ZIP Code

- key: `contact.home.zip` · pages: AddressPhone · kind: **missing**
- answer: 

### Q20 · Country/Region

- key: `contact.home.country` · pages: AddressPhone · kind: **missing**
- answer: 

### Q21 · Is your Mailing Address the same as your Home Address?

- key: `contact.mailing_same_as_home_ind` · pages: AddressPhone · kind: **missing**
- answer: 

### Q22 · Primary Phone Number

- key: `contact.primary_phone` · pages: AddressPhone · kind: **missing**
- answer: 

### Q23 · 其他电话：第二个号码、工作电话；没有就回“不适用”

- key: `contact.phones` · pages: AddressPhone · kind: **missing**
  - Secondary Phone Number: ?
  - Work Phone Number: ?
- answer: 

### Q24 · Other phone numbers in the last five years?

- key: `contact.other_phones_ind` · pages: AddressPhone · kind: **missing**
- answer: 

### Q25 · Email Address

- key: `contact.primary_email` · pages: AddressPhone · kind: **missing**
- answer: 

### Q26 · Other email addresses in the last five years?

- key: `contact.other_emails_ind` · pages: AddressPhone · kind: **missing**
- answer: 

### Q27 · 过去 5 年用过的社交媒体平台和用户名（DS-160 列表：Douban/Facebook/Instagram/LinkedIn/QZone/Reddit/Sina Weibo/Tencent Weibo/Twitter/YouTube…）

- key: `contact.social_media` · pages: AddressPhone · kind: **missing**
- answer: 

### Q28 · 过去 5 年用过的社交媒体平台+用户名（DS-160 列表：Douban/Facebook/Instagram/LinkedIn/QZone/Reddit/Sina Weibo/Tencent Weibo/Twitter/YouTube…；微信/小红书不在列表）

- key: `contact.social` · pages: AddressPhone · kind: **missing**
- answer: 

### Q29 · 美国联系人（H 类通常填雇主的主管/HR）：姓名、单位、关系、地址、电话、邮箱

- key: `app.us_contact` · pages: USContact · kind: **missing**
  - Contact Surnames: ?
  - Contact Given Names: ?
  - Organization Name: ?
  - Relationship to You: ?
  - Contact Address Line 1: ?
  - Contact City: ?
  - Contact State: ?
  - Contact ZIP: ?
  - Contact Phone: ?
  - Contact Email: ?
- answer: 

### Q30 · 父亲信息：拼音姓、拼音名、出生日期(YYYY-MM-DD)、目前是否在美国。最好放户口本/出生证明到 raw/inbox/

- key: `family.father` · pages: Relatives · kind: **missing**
  - Father's Surnames: ?
  - Father's Given Names: ?
  - Father's Date of Birth: ?
  - Is your father in the U.S.?: ?
- answer: 

### Q31 · 母亲信息：拼音姓、拼音名、出生日期(YYYY-MM-DD)、目前是否在美国

- key: `family.mother` · pages: Relatives · kind: **missing**
  - Mother's Given Names: ?
  - Mother's Date of Birth: ?
  - Is your mother in the U.S.?: ?
- answer: 

### Q32 · 在美国有没有直系亲属（配偶/未婚夫妻/子女/兄弟姐妹）？有的话给姓名、关系、身份

- key: `family.us_immediate_relatives_ind` · pages: Relatives · kind: **missing**
- answer: 

### Q33 · 在美国有没有其他亲戚？

- key: `family.us_other_relatives_ind` · pages: Relatives · kind: **missing**
- answer: 

### Q34 · Primary Occupation

- key: `employment.current.ds160_occupation` · pages: WorkEducation1 · kind: **missing**
- answer: 

### Q35 · Present Employer or School Name

- key: `employment.current.employer` · pages: WorkEducation1, TemporaryWork · kind: **missing**
  - Present Employer or School Name: ?
  - Name of Person/Company who Filed Petition: ?
  - Name of Employer: ?
- answer: 

### Q36 · Employer Street Address (Line 1)

- key: `employment.current.address.line1` · pages: WorkEducation1 · kind: **missing**
- answer: 

### Q37 · Employer City

- key: `employment.current.address.city` · pages: WorkEducation1, TemporaryWork · kind: **missing**
  - Employer City: ?
  - Worksite City: ?
- answer: 

### Q38 · Employer State/Province

- key: `employment.current.address.state_name` · pages: WorkEducation1 · kind: **missing**
- answer: 

### Q39 · Employer ZIP

- key: `employment.current.address.zip` · pages: WorkEducation1, TemporaryWork · kind: **missing**
  - Employer ZIP: ?
  - Worksite ZIP: ?
- answer: 

### Q40 · 雇主电话（DS-160 必填，可用公司总机）

- key: `employment.current.phone` · pages: WorkEducation1, TemporaryWork · kind: **missing**
  - Employer Phone Number: ?
  - Phone Number: ?
- answer: 

### Q41 · Employer Country/Region

- key: `employment.current.address.country` · pages: WorkEducation1 · kind: **missing**
- answer: 

### Q42 · Start Date

- key: `employment.current.start` · pages: WorkEducation1 · kind: **missing**
- answer: 

### Q43 · 当前月收入（当地货币，税前）

- key: `employment.current.monthly_income_usd` · pages: WorkEducation1, TemporaryWork · kind: **missing**
  - Monthly Income in Local Currency: ?
  - Monthly income (USD): ?
- answer: 

### Q44 · Briefly describe your duties

- key: `employment.current.duties_ds160` · pages: WorkEducation1 · kind: **missing**
- answer: 

### Q45 · Were you previously employed?

- key: `employment.previous_ind` · pages: WorkEducation2 · kind: **missing**
- answer: 

### Q46 · Attended any educational institutions at secondary level or above?

- key: `education.attended_ind` · pages: WorkEducation2 · kind: **missing**
- answer: 

### Q47 · 背景：是否属于某部落/氏族、参加过专业/社会/慈善组织、有枪械爆炸物核生化专长、参加过准军事/叛乱组织？全部否就回 No

- key: `declarations.background` · pages: WorkEducation3 · kind: **missing**
  - Belong to a clan or tribe?: ?
  - Belonged to/worked for any professional, social or charitable organization?: ?
  - Specialized skills (firearms, explosives, nuclear, biological, chemical)?: ?
  - Served in a paramilitary/insurgent organization?: ?
- answer: 

### Q48 · 你会说的语言（例：MANDARIN, ENGLISH）

- key: `contact.languages` · pages: WorkEducation3 · kind: **missing**
- answer: 

### Q49 · Traveled to any countries/regions in the last five years?

- key: `travel.countries_visited_5y_ind` · pages: WorkEducation3 · kind: **missing**
- answer: 

### Q50 · 是否服过兵役？（大学军训不算）

- key: `declarations.military_service` · pages: WorkEducation3 · kind: **missing**
- answer: 

### Q51 · 安全背景问题（传染病、犯罪记录、毒品、恐怖活动、移民欺诈、逾期滞留等约 25 题）——若全部为“否”，回复“安全问题全部 No”

- key: `declarations.security` · pages: SecurityandBackground1, SecurityandBackground2, SecurityandBackground3, SecurityandBackground4, SecurityandBackground5 · kind: **missing**
  - Part 1 (communicable disease, mental disorder, drug abuse): Disease: ?
  - Part 1 (communicable disease, mental disorder, drug abuse): Disorder: ?
  - Part 1 (communicable disease, mental disorder, drug abuse): Druguser: ?
  - Part 2 (criminal: arrests, drugs, prostitution, money laundering, trafficking): Arrested: ?
  - Part 2 (criminal: arrests, drugs, prostitution, money laundering, trafficking): ControlledSubstances: ?
  - Part 2 (criminal: arrests, drugs, prostitution, money laundering, trafficking): Prostitution: ?
  - Part 2 (criminal: arrests, drugs, prostitution, money laundering, trafficking): MoneyLaundering: ?
  - Part 2 (criminal: arrests, drugs, prostitution, money laundering, trafficking): HumanTrafficking: ?
  - Part 2 (criminal: arrests, drugs, prostitution, money laundering, trafficking): AssistedSevereTrafficking: ?
  - Part 2 (criminal: arrests, drugs, prostitution, money laundering, trafficking): HumanTraffickingRelated: ?
  - Part 3 (security: espionage, terrorism, genocide, torture, child soldiers, religious freedom, forced sterilization, organ harvesting): IllegalActivity: ?
  - Part 3 (security: espionage, terrorism, genocide, torture, child soldiers, religious freedom, forced sterilization, organ harvesting): TerroristActivity: ?
  - Part 3 (security: espionage, terrorism, genocide, torture, child soldiers, religious freedom, forced sterilization, organ harvesting): TerroristSupport: ?
  - Part 3 (security: espionage, terrorism, genocide, torture, child soldiers, religious freedom, forced sterilization, organ harvesting): TerroristOrg: ?
  - Part 3 (security: espionage, terrorism, genocide, torture, child soldiers, religious freedom, forced sterilization, organ harvesting): TerroristRel: ?
  - Part 3 (security: espionage, terrorism, genocide, torture, child soldiers, religious freedom, forced sterilization, organ harvesting): Genocide: ?
  - Part 3 (security: espionage, terrorism, genocide, torture, child soldiers, religious freedom, forced sterilization, organ harvesting): Torture: ?
  - Part 3 (security: espionage, terrorism, genocide, torture, child soldiers, religious freedom, forced sterilization, organ harvesting): ExViolence: ?
  - Part 3 (security: espionage, terrorism, genocide, torture, child soldiers, religious freedom, forced sterilization, organ harvesting): ChildSoldier: ?
  - Part 3 (security: espionage, terrorism, genocide, torture, child soldiers, religious freedom, forced sterilization, organ harvesting): ReligiousFreedom: ?
  - Part 3 (security: espionage, terrorism, genocide, torture, child soldiers, religious freedom, forced sterilization, organ harvesting): PopulationControls: ?
  - Part 3 (security: espionage, terrorism, genocide, torture, child soldiers, religious freedom, forced sterilization, organ harvesting): Transplant: ?
  - Part 4 (immigration: removal, fraud, failure to attend hearing, visa violation/overstay, deportation): RemovalHearing: ?
  - Part 4 (immigration: removal, fraud, failure to attend hearing, visa violation/overstay, deportation): ImmigrationFraud: ?
  - Part 4 (immigration: removal, fraud, failure to attend hearing, visa violation/overstay, deportation): FailToAttend: ?
  - Part 4 (immigration: removal, fraud, failure to attend hearing, visa violation/overstay, deportation): VisaViolation: ?
  - Part 4 (immigration: removal, fraud, failure to attend hearing, visa violation/overstay, deportation): Deport: ?
  - Part 5 (custody, illegal voting, tax renunciation, J-1 home residency, F-1 public school without reimbursement): ChildCustody: ?
  - Part 5 (custody, illegal voting, tax renunciation, J-1 home residency, F-1 public school without reimbursement): VotingViolation: ?
  - Part 5 (custody, illegal voting, tax renunciation, J-1 home residency, F-1 public school without reimbursement): RenounceExp: ?
  - Part 5 (custody, illegal voting, tax renunciation, J-1 home residency, F-1 public school without reimbursement): ExchangeVisitor: ?
  - Part 5 (custody, illegal voting, tax renunciation, J-1 home residency, F-1 public school without reimbursement): AttWoReimb: ?
- answer: 

### Q52 · H-1B 工作地点地址（与 LCA/I-129 一致）

- key: `employment.current.worksite_line1` · pages: TemporaryWork · kind: **missing**
- answer: 

### Q53 · Worksite State

- key: `employment.current.address.state` · pages: TemporaryWork · kind: **missing**
- answer: 
