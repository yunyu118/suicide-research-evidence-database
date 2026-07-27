"""High-precision lexical rules over abstract text.

These rules are deliberately *precision-oriented*: each pattern targets
language that authors use almost exclusively when reporting a particular kind
of study, so a hit is strong evidence while a miss is uninformative. They
serve two roles in SRED:

* as one of three label sources for the distant-supervision training set
  (see :mod:`sred.classify.distant`), and
* as an interpretable fallback for records with no MEDLINE indexing.

They are *not* the final classifier. A rules-only system over-fires on
abstracts that discuss methods they did not use ("unlike previous qualitative
studies, we..."), which is why rule labels are only trusted where they agree
with metadata or where no metadata exists.
"""

from __future__ import annotations

import re
from typing import Any


def _rx(*alts: str) -> re.Pattern[str]:
    return re.compile("|".join(alts), re.I)


# --- Stage 1: scientific communication vs other scholarly communication ----
NON_SCIENTIFIC = _rx(
    r"\bthis (?:editorial|commentary|book review|letter to the editor)\b",
    r"\bin this issue\b", r"\bwe are pleased to (?:announce|introduce)\b",
    r"\bthe (?:editors?|editorial board) (?:of|welcome)\b",
    r"\breviewed? (?:the )?book\b", r"\bobituar",
    r"\berratum\b", r"\bcorrigendum\b", r"\bretraction notice\b",
    r"\bauthors? repl(?:y|ies)\b", r"\bresponse to (?:the )?(?:letter|commentary)\b",
)

# --- Stage 2: empirical vs non-empirical ----------------------------------
EMPIRICAL = _rx(
    r"\bparticipants? (?:were|completed|reported|comprised)\b",
    r"\bwe (?:recruited|surveyed|interviewed|enrolled|sampled|analy[sz]ed data)\b",
    r"\bdata were (?:collected|analy[sz]ed|drawn|obtained)\b",
    r"\ba (?:total|sample) of \d[\d,]* (?:participants|patients|adolescents|adults|respondents|cases|records|individuals|veterans|students)\b",
    r"\b(?:n\s*=\s*\d|sample size)\b",
    r"\bcross[- ]sectional (?:study|survey|design)\b",
    r"\blongitudinal (?:study|design|cohort)\b",
    r"\brandomi[sz]ed (?:controlled )?trial\b",
    r"\bretrospective (?:chart|cohort|record) review\b",
    r"\bregistry (?:data|linkage)\b", r"\bpsychological autops(?:y|ies)\b",
    r"\bsemi-?structured interviews?\b", r"\bfocus groups?\b",
    r"\bthematic analysis\b", r"\bgrounded theory\b",
    r"\bwe conducted (?:a|an|two|three)\b",
    r"\bresults? (?:showed|indicated|revealed|suggest)\b",
    r"\bodds ratios?\b", r"\bhazard ratios?\b", r"\bregression\b",
    r"\bp\s*[<>=]\s*0?\.\d", r"\b95%\s*(?:CI|confidence interval)\b",
)

NON_EMPIRICAL = _rx(
    r"\bthis (?:paper|article|essay) (?:argues|proposes|offers|presents a (?:framework|model|theory)|considers|reflects)\b",
    r"\bconceptual (?:framework|analysis|paper|model)\b",
    r"\btheoretical (?:framework|paper|analysis|contribution)\b",
    r"\bwe (?:argue|propose a framework|theori[sz]e|reflect on)\b",
    r"\bnarrative review\b", r"\bcommentary\b", r"\bposition (?:paper|statement)\b",
    r"\bclinical (?:case )?vignette\b", r"\bpractice (?:guidance|reflection)\b",
    r"\bcall to action\b", r"\bviewpoint\b",
)

# --- Stage 3: methodology --------------------------------------------------
QUANT = _rx(
    r"\bregression\b", r"\blogistic\b", r"\bodds ratio\b", r"\bhazard ratio\b",
    r"\brisk ratio\b", r"\bchi[- ]squared?\b", r"\bANOVA\b", r"\bt-test\b",
    r"\bstructural equation model", r"\bmultilevel model", r"\blatent (?:class|profile|growth)\b",
    r"\bpropensity score\b", r"\btime[- ]series\b", r"\bpoisson\b", r"\bnegative binomial\b",
    r"\bsurvival analysis\b", r"\bcox (?:proportional|regression)\b",
    r"\bprevalence (?:of|rate)\b", r"\bincidence rate\b", r"\bstatistically significant\b",
    r"\bp\s*[<>=]\s*0?\.\d", r"\b95%\s*(?:CI|confidence interval)\b",
    r"\bmachine learning\b", r"\bpredictive model", r"\bAUC\b", r"\bpsychometric\b",
    r"\bfactor analysis\b", r"\bCronbach", r"\beffect size\b", r"\bcohen'?s d\b",
    r"\brandomi[sz]ed\b", r"\bcontrol(?:led)? (?:group|condition|trial)\b",
)

QUAL = _rx(
    r"\bqualitative (?:study|design|analysis|methods?|interviews?|approach|research)\b",
    r"\bsemi-?structured interviews?\b", r"\bin-?depth interviews?\b",
    r"\bfocus groups?\b", r"\bthematic analysis\b", r"\bcontent analysis\b",
    r"\bgrounded theory\b", r"\bphenomenolog", r"\bethnograph", r"\bnarrative analysis\b",
    r"\bdiscourse analysis\b", r"\binterpretative phenomenological\b", r"\bIPA\b",
    r"\bconstant comparative\b", r"\bpurposive sampl", r"\bsaturation was reached\b",
    r"\bparticipants described\b", r"\bemergent themes?\b", r"\bcoded (?:the )?transcripts?\b",
    r"\blived experience\b", r"\bcase stud(?:y|ies)\b",
)

MIXED = _rx(
    r"\bmixed[- ]methods?\b", r"\bqualitative and quantitative\b",
    r"\bquantitative and qualitative\b", r"\bconvergent (?:parallel )?design\b",
    r"\bexplanatory sequential\b", r"\bexploratory sequential\b",
    r"\btriangulat(?:ion|ed) (?:of )?(?:data|methods)\b",
)

REVIEW = _rx(
    r"\bsystematic review\b", r"\bmeta-?analys[ie]s\b", r"\bmeta-?regression\b",
    r"\bscoping review\b", r"\brapid review\b", r"\bumbrella review\b",
    r"\bPRISMA\b", r"\bmeta-?synthesis\b", r"\bnetwork meta-?analysis\b",
    r"\bwe searched (?:PubMed|MEDLINE|Embase|PsycINFO|Web of Science|Scopus)\b",
    r"\b(?:studies|articles|records) were (?:screened|included|identified)\b",
    r"\bpooled (?:effect|estimate|prevalence|odds)\b",
    r"\binclusion and exclusion criteria\b",
)

# --- SRED-specific extraction ---------------------------------------------
PREVENTION_LEVEL = {
    "universal": _rx(r"\buniversal (?:prevention|intervention|programme?|screening)\b",
                     r"\bpopulation[- ]level (?:intervention|prevention|strategy)\b",
                     r"\bpublic (?:health|awareness) campaign\b",
                     r"\bmeans restriction\b", r"\bmedia guidelines?\b",
                     r"\bschool[- ]based (?:universal|prevention) program"),
    "selective": _rx(r"\bselective (?:prevention|intervention)\b",
                     r"\bat[- ]risk (?:group|population|youth|veterans)\b",
                     r"\bhigh[- ]risk (?:group|population|sample)\b",
                     r"\bgatekeeper training\b"),
    "indicated": _rx(r"\bindicated (?:prevention|intervention)\b",
                     r"\bsafety plan(?:ning)?\b", r"\bcrisis (?:line|text|hotline|服务)\b",
                     r"\bbrief (?:contact|intervention) (?:after|following)\b",
                     r"\bfollow[- ]up (?:contacts?|care) after (?:a )?suicide attempt\b",
                     r"\bcaring (?:contacts|letters)\b"),
    "treatment": _rx(r"\b(?:CBT|DBT|CAMS|cognitive[- ]behavio(?:u)?ral therapy|dialectical behavio(?:u)?r therapy)\b",
                     r"\bketamine\b", r"\bclozapine\b", r"\blithium\b",
                     r"\bpharmacotherap", r"\bpsychotherap", r"\binpatient (?:treatment|admission)\b",
                     r"\belectroconvulsive\b"),
    "postvention": _rx(r"\bpostvention\b", r"\bsuicide bereave", r"\bsurvivors of suicide loss\b",
                       r"\bbereaved by suicide\b", r"\bafter(?:math|care) of a suicide\b"),
}

OUTCOME_CONSTRUCT = {
    "suicide_death": _rx(r"\bsuicide (?:death|mortality|rate)s?\b", r"\bcompleted suicide\b",
                         r"\bdied by suicide\b", r"\bsuicide[- ]related (?:death|mortality)\b",
                         r"\bfatal self[- ]harm\b"),
    "suicide_attempt": _rx(r"\bsuicide attempts?\b", r"\battempted suicide\b",
                           r"\battempters?\b", r"\bnon-?fatal self[- ]harm\b"),
    "suicidal_ideation": _rx(r"\bsuicidal ideation\b", r"\bsuicidal thoughts?\b",
                             r"\bthoughts of suicide\b", r"\bdeath wish\b",
                             r"\bpassive suicidal\b"),
    "non_suicidal_self_injury": _rx(r"\bnon-?suicidal self-?injur", r"\bNSSI\b",
                                    r"\bself-?mutilat", r"\bself-?cutting\b"),
    "self_harm_undifferentiated": _rx(r"\bself-?harm\b", r"\bdeliberate self-?harm\b",
                                      r"\bself-?poisoning\b"),
    "suicide_bereavement": _rx(r"\bsuicide bereave", r"\bsuicide loss survivors?\b",
                               r"\bbereaved by suicide\b", r"\bpostvention\b"),
    "attitudes_or_stigma": _rx(r"\bstigma\b", r"\battitudes? toward", r"\bliteracy\b",
                               r"\bknowledge and attitudes\b"),
    "service_use_or_care_process": _rx(r"\bemergency department (?:visits?|presentations?)\b",
                                       r"\bservice (?:use|utili[sz]ation)\b",
                                       r"\bhelp[- ]seeking\b", r"\bcontinuity of care\b",
                                       r"\btreatment engagement\b", r"\breferral\b"),
}

POPULATION = {
    "youth_adolescent": _rx(r"\badolescents?\b", r"\byouths?\b", r"\bteenagers?\b",
                            r"\bschool students?\b", r"\bchildren\b", r"\bcollege students?\b",
                            r"\buniversity students?\b", r"\byoung (?:people|adults)\b"),
    "older_adult": _rx(r"\bolder adults?\b", r"\belderly\b", r"\bgeriatric\b",
                       r"\blate[- ]life\b", r"\baged 65\b", r"\bseniors?\b"),
    "veteran_military": _rx(r"\bveterans?\b", r"\bmilitary\b", r"\bservice members?\b",
                            r"\bactive duty\b", r"\bsoldiers?\b", r"\bVeterans Health\b", r"\bVHA\b"),
    "clinical_psychiatric": _rx(r"\bpsychiatric (?:inpatients?|patients?|admission)\b",
                                r"\binpatient(?:s)?\b", r"\bmental health service users?\b",
                                r"\bschizophrenia\b", r"\bbipolar\b", r"\bmajor depress"),
    "primary_care": _rx(r"\bprimary care\b", r"\bgeneral practi", r"\bfamily (?:medicine|physicians?)\b"),
    "justice_involved": _rx(r"\bprison(?:ers?)?\b", r"\bincarcerat", r"\bjail\b",
                            r"\bcorrectional\b", r"\bjustice[- ]involved\b", r"\bdetention\b"),
    "lgbtq": _rx(r"\bLGBTQ?\+?\b", r"\bsexual minorit", r"\bgender minorit", r"\btransgender\b",
                 r"\bgay\b", r"\blesbian\b", r"\bbisexual\b", r"\bnon-?binary\b"),
    "indigenous": _rx(r"\bindigenous\b", r"\bAboriginal\b", r"\bNative American\b",
                      r"\bAmerican Indian\b", r"\bFirst Nations?\b", r"\bMāori|Maori\b",
                      r"\bAlaska Native\b", r"\bTorres Strait\b"),
    "racial_ethnic_minority": _rx(r"\bBlack (?:adults?|youth|Americans?)\b", r"\bAfrican American\b",
                                  r"\bLatin[oax]+\b", r"\bHispanic\b", r"\bAsian American\b",
                                  r"\bracial(?:/| and )ethnic (?:minorit|disparit)",
                                  r"\bethnic minorit"),
    "rural": _rx(r"\brural\b", r"\bremote (?:communit|area)", r"\bnon-?metropolitan\b"),
    "occupational": _rx(r"\bfarmers?\b", r"\bphysicians?\b", r"\bnurses?\b", r"\bpolice officers?\b",
                        r"\bfirst responders?\b", r"\bconstruction workers?\b",
                        r"\boccupational (?:group|cohort)\b", r"\bworkplace\b"),
    "perinatal": _rx(r"\bperinatal\b", r"\bpostpartum\b", r"\bpregnan", r"\bmaternal\b"),
}

STUDY_DESIGN = {
    "rct": _rx(r"\brandomi[sz]ed (?:controlled )?trial\b", r"\bRCT\b",
               r"\brandomly (?:assigned|allocated)\b", r"\bcluster[- ]randomi[sz]ed\b"),
    "quasi_experimental": _rx(r"\bquasi-?experimental\b", r"\bpre-?post design\b",
                              r"\bdifference[- ]in[- ]difference", r"\binterrupted time[- ]series\b",
                              r"\bnon-?randomi[sz]ed (?:trial|controlled)\b"),
    "cohort_prospective": _rx(r"\bprospective cohort\b", r"\blongitudinal cohort\b",
                              r"\bfollowed (?:up )?for \d+ (?:years?|months?)\b",
                              r"\bbirth cohort\b", r"\bprospective(?:ly)? follow"),
    "case_control": _rx(r"\bcase-?control\b", r"\bmatched controls?\b",
                        r"\bnested case-?control\b"),
    "cross_sectional": _rx(r"\bcross-?sectional\b", r"\bsurvey of \d", r"\bnational survey\b",
                           r"\bself-?report questionnaires?\b"),
    "ecological_timeseries": _rx(r"\btime[- ]series\b", r"\becological (?:study|analysis)\b",
                                 r"\bjoinpoint\b", r"\bARIMA\b", r"\btrends? in suicide rates?\b",
                                 r"\bage-?period-?cohort\b"),
    "registry_linkage": _rx(r"\bregistry\b", r"\bregister[- ]based\b", r"\brecord linkage\b",
                            r"\bnational registers?\b", r"\badministrative (?:data|claims)\b",
                            r"\belectronic health records?\b", r"\bclaims data\b"),
    "psychological_autopsy": _rx(r"\bpsychological autops(?:y|ies)\b"),
    "systematic_review_meta_analysis": _rx(r"\bsystematic review\b", r"\bmeta-?analys[ie]s\b",
                                           r"\bPRISMA\b"),
    "scoping_narrative_review": _rx(r"\bscoping review\b", r"\bnarrative review\b",
                                    r"\bliterature review\b", r"\brapid review\b"),
    "simulation_modelling": _rx(r"\bsimulation model", r"\bagent-?based model",
                                r"\bmicrosimulation\b", r"\bcost-?effectiveness (?:model|analysis)\b",
                                r"\bMarkov model"),
    "psychometric": _rx(r"\bpsychometric propert", r"\bvalidat(?:ion|ing) (?:of )?(?:the )?(?:scale|instrument|measure)\b",
                        r"\bfactor structure\b", r"\breliability and validity\b",
                        r"\bconfirmatory factor analysis\b"),
    "qualitative_interview": _rx(r"\bsemi-?structured interviews?\b", r"\bin-?depth interviews?\b",
                                 r"\bfocus groups?\b"),
    "mixed_methods": MIXED,
}

SDOH_DOMAIN = {
    "economic_stability": _rx(r"\bunemploy", r"\bpoverty\b", r"\bincome (?:inequality|level)\b",
                              r"\bsocio-?economic (?:status|position|disadvantage)\b",
                              r"\bfinancial (?:strain|hardship|difficult)", r"\bdebt\b",
                              r"\brecession\b", r"\bausterity\b", r"\bjob (?:loss|insecurity)\b",
                              r"\bemployment status\b", r"\bwelfare\b", r"\bminimum wage\b"),
    "education_access": _rx(r"\beducational attainment\b", r"\bschool (?:dropout|connectedness|climate)\b",
                            r"\byears of (?:education|schooling)\b", r"\bacademic (?:pressure|stress)\b"),
    "healthcare_access": _rx(r"\baccess to (?:mental health )?(?:care|services|treatment)\b",
                             r"\bhealth insurance\b", r"\buninsured\b", r"\bMedicaid\b",
                             r"\btreatment gap\b", r"\bunmet need\b", r"\bservice availability\b",
                             r"\bworkforce shortage\b"),
    "neighborhood_environment": _rx(r"\bneighbo(?:u)?rhood\b", r"\bbuilt environment\b",
                                    r"\barea[- ]level deprivation\b", r"\bgreen space\b",
                                    r"\bcommunity disadvantage\b", r"\bsegregation\b",
                                    r"\bpopulation density\b", r"\bair pollution\b",
                                    r"\bheat|temperature\b"),
    "social_community_context": _rx(r"\bsocial (?:support|isolation|connect|capital|cohesion|network)\b",
                                    r"\blonelin", r"\bbelonging", r"\bfamily (?:conflict|cohesion)\b",
                                    r"\bbullying\b", r"\bpeer victimi[sz]ation\b",
                                    r"\badverse childhood experiences?\b", r"\bACEs?\b",
                                    r"\bintimate partner violence\b", r"\bmarital status\b"),
    "discrimination_racism": _rx(r"\bdiscriminat", r"\bracism\b", r"\bmicroaggress",
                                 r"\bminority stress\b", r"\bstructural racism\b",
                                 r"\bhomophobi|transphobi", r"\bhistorical trauma\b",
                                 r"\bcolonial"),
    "housing_homelessness": _rx(r"\bhomeless", r"\bhousing (?:instability|insecurity|eviction)\b",
                                r"\beviction\b", r"\bforeclosure\b", r"\bunstably housed\b"),
    "food_insecurity": _rx(r"\bfood insecurity\b", r"\bhunger\b", r"\bfood deserts?\b"),
    "incarceration": _rx(r"\bincarcerat", r"\bprison\b", r"\bjail\b", r"\bcriminal justice\b",
                         r"\bparole\b", r"\bprobation\b"),
    "immigration_status": _rx(r"\bimmigrant", r"\bmigrant", r"\brefugee", r"\basylum seek",
                              r"\bundocumented\b", r"\bacculturation\b"),
    "firearm_access_means": _rx(r"\bfirearms?\b", r"\bgun (?:ownership|access|law|storage|violence)\b",
                                r"\bmeans (?:restriction|safety)\b", r"\bsafe storage\b",
                                r"\bpesticide (?:ban|restriction)\b", r"\bbarrier",
                                r"\bpaacetamol|paracetamol pack\b"),
    "digital_social_media": _rx(r"\bsocial media\b", r"\bonline (?:communit|forum|content)\b",
                                r"\binternet use\b", r"\bcyberbullying\b", r"\bsmartphone\b",
                                r"\bdigital (?:intervention|technolog)\b", r"\bTikTok|Instagram|Twitter|Reddit\b"),
}

MEANS_FOCUS = {
    "firearm": _rx(r"\bfirearms?\b", r"\bgun\b", r"\bhandgun\b", r"\bshooting\b"),
    "poisoning_overdose": _rx(r"\boverdose\b", r"\bself-?poison", r"\bintoxicat",
                              r"\bparacetamol\b", r"\bacetaminophen\b", r"\bopioid\b",
                              r"\bmedication ingestion\b"),
    "pesticide": _rx(r"\bpesticides?\b", r"\bparaquat\b", r"\borganophosphat", r"\bherbicide\b"),
    "hanging": _rx(r"\bhanging\b", r"\bstrangulat", r"\bsuffocat", r"\bligature\b"),
    "jumping": _rx(r"\bjumping (?:from|off)\b", r"\bbridges?\b", r"\bfall from (?:a )?height\b",
                   r"\bhigh[- ]rise\b"),
    "drowning": _rx(r"\bdrowning\b"),
}


def match_labels(text: str, patterns: dict[str, re.Pattern[str]],
                 multi: bool = True) -> list[str] | str | None:
    """Return every (or the first) label whose pattern matches ``text``."""
    if not text:
        return [] if multi else None
    hits = [label for label, rx in patterns.items() if rx.search(text)]
    if multi:
        return hits
    return hits[0] if hits else None


def rule_labels(title: str, abstract: str) -> dict[str, Any]:
    """Apply the full rule battery to one record."""
    text = f"{title or ''}. {abstract or ''}"

    # Methodology precedence mirrors the classification hierarchy: a review is
    # a review even if it reports pooled statistics; a study that names both
    # traditions is mixed-methods even if quantitative language dominates.
    if REVIEW.search(text):
        method = "review"
    elif MIXED.search(text):
        method = "mixed"
    else:
        q_hits = len(QUANT.findall(text))
        l_hits = len(QUAL.findall(text))
        if q_hits == 0 and l_hits == 0:
            method = None
        elif l_hits > q_hits:
            method = "qualitative"
        elif q_hits > l_hits:
            method = "quantitative"
        else:
            method = "mixed"

    empirical = None
    if EMPIRICAL.search(text):
        empirical = True
    if NON_EMPIRICAL.search(text) and not EMPIRICAL.search(text):
        empirical = False

    sdoh = match_labels(text, SDOH_DOMAIN)
    means = match_labels(text, MEANS_FOCUS)

    return {
        "rule_is_scientific": not bool(NON_SCIENTIFIC.search(text)),
        "rule_is_empirical": empirical,
        "rule_methodology": method,
        "prevention_level": match_labels(text, PREVENTION_LEVEL, multi=False) or "not_applicable",
        "outcome_construct": match_labels(text, OUTCOME_CONSTRUCT) or ["not_specified"],
        "population": match_labels(text, POPULATION) or ["general_population"],
        "study_design": match_labels(text, STUDY_DESIGN),
        "sdoh_focus": bool(sdoh),
        "sdoh_domain": sdoh or ["none"],
        "means_focus": means or ["none"],
    }
