import mistletoe
import mellea
import re
import os
import openai

from mellea.stdlib.base import Context
from mellea.stdlib.requirement import Requirement
from mellea import generative
RITS_API_KEY = os.environ.get("RITS_API_KEY")
openai_url = "https://inference-3scale-apicast-production.apps.rits.fmaas.res.ibm.com/gpt-oss-120b"
openai_model = "openai/gpt-oss-120b"
deepseek_url = "https://inference-3scale-apicast-production.apps.rits.fmaas.res.ibm.com/deepseek-v3-h200"
deepseek_model = "deepseek-ai/DeepSeek-V3"


state_statute_citations = [
    "Ala. Code",
    r"(Alaska Stat\.|AS)",
    r"(Ariz\. Rev\. Stat\. Ann\.|A\.R\.S\.)",
    "Ark. Code Ann.",
    r"Cal\.(.*Code| HSC)",
    #r"Cal\. (Bus\. & Prof\. Code|Civ\. Code|Civ\. Proc\. Code|Com\. Code|Corp\. Code|Educ\. Code|Elec\. Code|Evid\. Code|Fam\. Code|Fin\. Code|Fish & Game Code|Food & Agric\. Code|Gov't\. Code|Harb\. & Nav\. Code|Health & Safety Code|HSC|Ins\. Code|Lab\. Code|Mil\. & Vet\. Code|Penal Code|Prob\. Code|Pub\. Cont\. Code|Pub\. Res\. Code|Pub\. Util\. Code|Rev\. & Tax\. Code|Sts\. & High\. Code|Unemp\. Ins\. Code|Veh\. Code|Water Code|Welf\. & Inst\. Code)"
    r"(Colo\. Rev\. Stat\.|C\.R\.S\.)",
    "Conn. Gen. Stat.",
    "Ga. Code Ann.",
    r"(Haw\. Rev\. Stat\.|HRS)",
    "Idaho Code",
    "Ind. Code",
    r"(Iowa Code|I\.C\.A\.)",
    "Kan. Stat. Ann.",
    r"(Ky\. Rev\. Stat\. Ann\.|KRS)",
    "La. R.S.",
    "Md. Code",
    r"(Mass\. Gen\. Laws|MGL)",
    r"(Mich\. Comp\. Laws|MCL)",
    "Me. Rev. Stat. Ann.",
    "MINN. STAT.",
    "Miss. Code Ann.",
    "Mo. Rev. Stat.",
    r"(Mont\. Code Ann\.|MCA)",
    "Neb. Rev. Stat.",
    r"(Nev\. Rev\. Stat\.|N\.R\.S\.)",
    "N.H. Rev. Stat. Ann.",
    "N.J. Stat.",
    "N.M. Stat. Ann.",
    r"N\.Y\.(.*(Law|Act)| (C\.P\.L\.R\.|CPLR|E\.P\.T\.L\.|EPTL|S\.C\.P\.A\.|SCPA|U\.C\.C\.|UCC))",
    r"(N\.C\. Gen\. Stat\.|N\.C\.G\.S\.)",
    r"N\.D\.(C\.C\.| Cent\. Code)",
    "Ohio Rev. Code Ann.",
    r"(Okla\.|OK) Stat\.",
    "Or. Rev. Stat.",
    "R.I. Gen. Laws",
    "S.C. Code Ann.",
    r"(S\.D\. Codified Laws|SDCL)",
    r"(Tenn\. Code Ann\.|T\.C\.A\.)",
    r"Texas (.*Code|.*Stat.)",
    r"Utah Code (Ann\.|Annotated)",
    "Va. Code Ann.",
    r"(Vt\. Stat\. Ann\.|VSA)",
    r"(Wash\. Rev\. Code|RCW)",
    "W. Va. Code",
    "Wis. Stat.",
    "Wyo. Stat. Ann.",
    "D.C. Code"
]

title_before_code = [
    "U.S.C.",
    "Del. C.",
    "ILCS",
    "OK ST",
    "Pa. C.S.",
]

florida = r"\u00a7 [1-9][0-9]*\.[1-9][0-9]* (Fla\. Stat\.|F\.S\.)"

def parse_statutes(file: str) -> list[str]:
    citations = []
    # find all matches in file
    for statute in state_statute_citations:
        matches = [m.start() for m in re.finditer(statute, file)]
        for match in matches:
            end = re.search(r"\s\(.*\)", file[match+1:])
            if end is None:
                raise Exception(f"Could not find closing parenthesis for statute match: {statute}")
            citation = file[match:match+end.end()+1]
            citations.append(citation)
    for statute in title_before_code:
        pattern = statute
        matches = [m.start() for m in re.finditer(pattern, file)]
        for match in matches:
            end = re.search(r"\s\(.*\)", file[match+1:])
            # what if year not included at all, and it captures future paren
            if end is None:
                if statute == "U.S.C.":
                    end_match = re.search(r"\u00a7 [1-9][0-9]*(-[1-9][0-9]*)*\s", file[match+1:])
                    if end_match is not None:
                        end = match + 1 + end_match.end() - 1
                if end is None:
                    raise Exception(f"Could not find proper closing for statute match: {statute}")
            start = file.rfind(" ", 0, match-1) # find the last space before the match
            citation = file[start+1:match+end.end()+1]
            citations.append(citation)
    # special case for florida
    matches = [m.start() for m in re.finditer(florida, file)]
    for match in matches:
        end = file.find(")", match)
        print(file[match:])
        if end == -1:
            raise Exception(f"Could not find closing parenthesis for statute match: {statute}")
        start = file.rfind(" ", 0, match-1) # find the last space before the match
        citation = file[start+1:end+1]
        citations.append(citation)
    return citations


# doesn't work but will leave this here for now
def verify_statutes(citations: list[str]) -> list[bool]:
    statute_exists = [] 
    v1 = openai.OpenAI(api_key=RITS_API_KEY, base_url=f"{openai_url}/v1", default_headers={"RITS_API_KEY": RITS_API_KEY})
    v2 = openai.OpenAI(api_key=RITS_API_KEY, base_url=f"{deepseek_url}/v1", default_headers={"RITS_API_KEY": RITS_API_KEY})
    check_consistency = mellea.start_session(model_options={"temperature": 0})
    for citation in citations:
        response1 = v1.chat.completions.create(
            model=openai_model,
            messages=[
                {"role": "user", "content": f"Can you tell me what is this statute about: {citation}"}
            ],
            temperature=0.1,
        ).choices[0].message.content
        response2 = v2.chat.completions.create(
            model=deepseek_model,
            messages=[
                {"role": "user", "content": f"Can you tell me what is this statute about: {citation}"}
            ],
            temperature=0.1,
        ).choices[0].message.content
        consistent = classify_response(check_consistency, response1=response1, response2=response2)
        if not consistent:
            print(citation)
            print("Response 1:", response1)
            print("Response 2:", response2)
        statute_exists.append(consistent)
    return [(i, j) for i, j in zip(citations, statute_exists)]
        
@generative
def classify_response(response1: str, response2: str) -> bool:
    """classify if the two responses are consistent with each other for the same statute"""
    ...


short = """
Refer to 18 U.S.C. § 111 (2015) for federal assault on a federal officer.
Ariz. Rev. Stat. Ann. § 112-1001 (2025) is hopefully a fictional statute and does not exist.
Cal. Harb. & Nav. Code § 399 (1937). 
Cal. Penal Code § 653.26 (2022), assault is defined as an unlawful attempt to commit a violent injury.
Cal. Penal Code § 653.30 (2022)
"""


text =  """
Under T.C.A. § 39-13-101 (2021), assault includes intentional bodily injury to another.
Compare O.C.G.A. § 16-5-20 (2018) with Fla. Stat. § 784.011 (2020) for variations in assault definitions.
See also A.R.S. § 13-1203 (2019), which includes offensive physical contact as assault.
In Cal. Penal Code § 240 (2022), assault is defined as an unlawful attempt to commit a violent injury.
Under 720 ILCS 5/12-1 (2017), Illinois law focuses on apprehension rather than physical contact.
Refer to 18 U.S.C. § 111 (2015) for federal assault on a federal officer.
Ariz. Rev. Stat. Ann. § 112-1001 (2025) is hopefully a fictional statute and does not exist.
"""

legal_text = """Under the provisions of the Civil Rights Act, individuals are protected against 
discrimination based on race, color, religion, sex, or national origin. See 42 U.S.C. § 2000e-2 (2018). 
This protection extends to employment practices, including hiring and promotion decisions. 

Additionally, the Americans with Disabilities Act provides safeguards for individuals with disabilities. 
See 42 U.S.C. § 12112 (2018). Employers must make reasonable accommodations unless such accommodations 
would impose an undue hardship. See id. § 12111(10). 

Moreover, under the Fair Labor Standards Act, employees are entitled to minimum wage and overtime pay. 
See 29 U.S.C. §§ 206–207 (2018). These rights are enforced through the Department of Labor and private lawsuits. 

In matters involving securities fraud, the Securities Exchange Act of 1934 governs such cases. 
See 15 U.S.C. § 78j(b) (2018). Rule 10b-5, promulgated under this statute, prohibits fraudulent activities 
in connection with the purchase or sale of securities. See 17 C.F.R. § 240.10b-5 (2023). 

With regard to immigration, the Immigration and Nationality Act sets forth the legal framework for removal proceedings. 
See 8 U.S.C. § 1229a (2020). The statute outlines due process rights and procedures for noncitizens. 

Furthermore, under the Internal Revenue Code, individuals must file income tax returns annually. 
See 26 U.S.C. § 6012 (2022). Willful failure to file may result in criminal penalties. See id. § 7203. 

In criminal law, the federal sentencing guidelines are advisory but must be considered by courts. 
See 18 U.S.C. § 3553(a) (2018). Courts must impose sentences that are sufficient but not greater than necessary 
to comply with the statutory purposes of sentencing. See id. 

Additionally, under the Freedom of Information Act, individuals may request access to federal agency records. 
See 5 U.S.C. § 552 (2020). Agencies must respond within a reasonable period of time and provide records 
unless an exemption applies. 

Finally, the Uniform Commercial Code (U.C.C.) governs many aspects of commercial transactions. 
See U.C.C. § 2-207 (Am. Law Inst. & Unif. Law Comm’n 2022). Section 2-207 modifies the common law 
'mirror image rule' and allows for contract formation even when acceptance includes additional or different terms."""


citations = parse_statutes(short)
exists = verify_statutes(citations)
print(exists)


