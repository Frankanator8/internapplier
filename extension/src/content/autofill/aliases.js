// Field-matching aliases. Each key matches a profile field returned by
// /autofill/fields. Patterns are tested against a normalized label string
// (lowercased, whitespace-collapsed) built from <label>, name, id,
// placeholder, and aria-label.
const ALIASES = [
  ["first_name",          [/first\s*name/, /given\s*name/, /\bfname\b/]],
  ["last_name",           [/last\s*name/, /family\s*name/, /surname/, /\blname\b/]],
  ["preferred_name",      [/preferred\s*name/, /nickname/]],
  ["pronouns",            [/pronouns?/]],
  ["email",               [/e[-\s]?mail/]],
  ["phone",               [/phone/, /mobile/, /telephone/, /\btel\b/]],
  ["address1",            [/address\s*(line)?\s*1/, /street\s*address/, /\baddress\b(?!.*2)/]],
  ["address2",            [/address\s*(line)?\s*2/, /apt|apartment|suite|unit/]],
  ["city",                [/city|town|locality/]],
  ["state",               [/state|province|region/]],
  ["postal_code",         [/postal|zip/]],
  ["country",             [/country/]],
  ["linkedin",            [/linked\s*in/]],
  ["website",             [/website|portfolio|personal\s*site|homepage/]],
  ["github",              [/github/]],
  ["earliest_start_date", [/start\s*date|availability|available|earliest/]],
  ["desired_salary",      [/salary|compensation|expected\s*pay|desired\s*pay/]],
  ["date_of_birth",       [/date\s*of\s*birth|birth\s*date|\bdob\b/]],
  ["employment_status",   [/employment\s*status|current\s*employment/]],
  ["work_authorization",  [/work\s*authorization|authorized\s*to\s*work|us\s*work\s*auth/]],
  ["require_sponsorship", [/sponsorship|visa\s*sponsor|require.*visa/]],
  ["willing_to_relocate", [/relocat/]],
  ["gender",              [/\bgender\b/]],
  ["ethnicity",           [/ethnic|race/]],
  ["veteran_status",      [/veteran/]],
  ["disability_status",   [/disab/]],
  ["company",             [/company|employer|organization|organisation/]],
  ["role",                [/job\s*title|position|role/]],
  ["description",         [/cover\s*letter|why\s*(do\s*you\s*)?(want|interested)|message|about\s*you/]],
];

function labelTextFor(el) {
  const parts = [];
  if (el.labels && el.labels.length) {
    for (const l of el.labels) parts.push(l.textContent || "");
  } else if (el.id) {
    const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
    if (l) parts.push(l.textContent || "");
  }
  let p = el.parentElement;
  for (let i = 0; i < 3 && p; i++, p = p.parentElement) {
    if (p.tagName === "LABEL") { parts.push(p.textContent || ""); break; }
  }
  parts.push(el.getAttribute("aria-label") || "");
  parts.push(el.getAttribute("placeholder") || "");
  parts.push(el.getAttribute("name") || "");
  parts.push(el.getAttribute("id") || "");
  return normalize(parts.join(" "));
}

function matchKey(label) {
  for (const [key, patterns] of ALIASES) {
    for (const pat of patterns) {
      if (pat.test(label)) return key;
    }
  }
  return null;
}
