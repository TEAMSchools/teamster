from pydantic import AliasChoices, BaseModel, Field

FILLER_FIELD = Field(
    default=None,
    validation_alias=AliasChoices(
        "filler_1",
        "filler_10",
        "filler_11",
        "filler_12",
        "filler_13",
        "filler_14",
        "filler_15",
        "filler_16",
        "filler_17",
        "filler_18",
        "filler_19",
        "filler_2",
        "filler_20",
        "filler_21",
        "filler_22",
        "filler_23",
        "filler_24",
        "filler_25",
        "filler_26",
        "filler_27",
        "filler_28",
        "filler_29",
        "filler_3",
        "filler_30",
        "filler_31",
        "filler_32",
        "filler_33",
        "filler_34",
        "filler_35",
        "filler_36",
        "filler_37",
        "filler_38",
        "filler_39",
        "filler_4",
        "filler_40",
        "filler_41",
        "filler_42",
        "filler_43",
        "filler_44",
        "filler_45",
        "filler_46",
        "filler_47",
        "filler_48",
        "filler_49",
        "filler_5",
        "filler_50",
        "filler_51",
        "filler_52",
        "filler_53",
        "filler_54",
        "filler_55",
        "filler_56",
        "filler_57",
        "filler_58",
        "filler_59",
        "filler_6",
        "filler_60",
        "filler_61",
        "filler_62",
        "filler_63",
        "filler_64",
        "filler_65",
        "filler_66",
        "filler_67",
        "filler_68",
        "filler_69",
        "filler_7",
        "filler_70",
        "filler_71",
        "filler_72",
        "filler_73",
        "filler_74",
        "filler_75",
        "filler_76",
        "filler_77",
        "filler_78",
        "filler_79",
        "filler_8",
        "filler_80",
        "filler_81",
        "filler_82",
        "filler_83",
        "filler_84",
        "filler_85",
        "filler_86",
        "filler_87",
        "filler_88",
        "filler_89",
        "filler_9",
        "filler_90",
        "filler_91",
        "filler_92",
        "filler_93",
        "filler",
        "filler1",
        "filler10",
        "filler11",
        "filler12",
        "filler13",
        "filler14",
        "filler15",
        "filler16",
        "filler17",
        "filler18",
        "filler19",
        "filler2",
        "filler20",
        "filler21",
        "filler22",
        "filler23",
        "filler24",
        "filler25",
        "filler26",
        "filler27",
        "filler28",
        "filler29",
        "filler3",
        "filler30",
        "filler31",
        "filler32",
        "filler33",
        "filler34",
        "filler35",
        "filler36",
        "filler37",
        "filler38",
        "filler39",
        "filler4",
        "filler5",
        "filler6",
        "filler7",
        "filler8",
        "fillerfield_1",
        "fillerfield_10",
        "fillerfield_11",
        "fillerfield_12",
        "fillerfield_13",
        "fillerfield_14",
        "fillerfield_15",
        "fillerfield_16",
        "fillerfield_17",
        "fillerfield_18",
        "fillerfield_19",
        "fillerfield_2",
        "fillerfield_20",
        "fillerfield_21",
        "fillerfield_22",
        "fillerfield_23",
        "fillerfield_24",
        "fillerfield_25",
        "fillerfield_26",
        "fillerfield_27",
        "fillerfield_28",
        "fillerfield_29",
        "fillerfield_3",
        "fillerfield_30",
        "fillerfield_4",
        "fillerfield_5",
        "fillerfield_6",
        "fillerfield_7",
        "fillerfield_8",
        "fillerfield_9",
        "fillerfield",
        "fillerfield1",
        "fillerfield2",
        "fillerfield4",
        "fillerfield5",
        "fillerfield7",
    ),
)


class PARCC(BaseModel):
    accountabledistrictcode: str | None = None
    accountabledistrictname: str | None = None
    accountableorganizationaltype: str | None = None
    accountableschoolcode: str | None = None
    accountableschoolname: str | None = None
    administrationdirectionsclarifiedinstudentsnativelanguage: str | None = None
    administrationdirectionsreadaloudinstudentsnativelanguage: str | None = None
    alternaterepresentationpapertest: str | None = None
    americanindianoralaskanative: str | None = None
    answermasking: str | None = None
    answersrecordedintestbook: str | None = None
    answersrecordedintestbooklet: str | None = None
    asian: str | None = None
    aslvideo: str | None = None
    assessmentgrade: str | None = None
    assessmentyear: str | None = None
    assistivetechnologynonscreenreader: str | None = None
    assistivetechnologyscreenreader: str | None = None
    attemptcreatedate: str | None = None
    batteryformid: str | None = None
    birthdate: str | None = None
    blackorafricanamerican: str | None = None
    brailleresponse: str | None = None
    braillewithtactilegraphics: str | None = None
    calculationdeviceandmathematicstools: str | None = None
    classname: str | None = None
    closedcaptioningforela: str | None = None
    closedcaptioningforelal: str | None = None
    colorcontrast: str | None = None
    datefirstenrolledinusschool: str | None = None
    economicdisadvantagestatus: str | None = None
    elaccommodation: str | None = None
    elaconstructedresponse: str | None = None
    elalconstructedresponse: str | None = None
    elalselectedresponseortechnologyenhanceditems: str | None = None
    elaselectedresponseortechnologyenhanceditems: str | None = None
    electronicbrailleresponse: str | None = None
    elexemptfromtakingela: str | None = None
    elexemptfromtakingelal: str | None = None
    emergencyaccommodation: str | None = None
    englishlearneraccommodatedresponses: str | None = None
    englishlearnerel: str | None = None
    extendedtime: str | None = None
    federalraceethnicity: str | None = None
    firsthighschoolmathassessment: str | None = None
    firstname: str | None = None
    formeriep: str | None = None
    frequentbreaks: str | None = None
    gender: str | None = None
    giftedandtalented: str | None = None
    gradelevelwhenassessed: str | None = None
    hispanicorlatinoethnicity: str | None = None
    home_language: str | None = None
    homeless: str | None = None
    humanreaderorhumansigner: str | None = None
    humansignerfortestdirections: str | None = None
    iepexemptfrompassing: str | None = None
    languagecode: str | None = None
    largeprint: str | None = None
    lastorsurname: str | None = None
    localstudentidentifier: str | None = None
    mathematicsresponse: str | None = None
    mathematicsresponseel: str | None = None
    mathematicsscienceaccommodatedresponse: str | None = None
    middlename: str | None = None
    migrantstatus: str | None = None
    monitortestresponse: str | None = None
    multipletestregistration: str | None = None
    nativehawaiianorotherpacificislander: str | None = None
    njelstatus: str | None = None
    njnotattemptflag: str | None = None
    nottestedcode: str | None = None
    nottestedreason: str | None = None
    onlineformid: str | None = None
    onlinepcr1: str | None = None
    onlinepcr2: str | None = None
    paperattemptcreatedate: str | None = None
    paperformid: str | None = None
    paperpcr1: str | None = None
    paperpcr2: str | None = None
    papersection1numberofattempteditems: str | None = None
    papersection1totaltestitems: str | None = None
    papersection2numberofattempteditems: str | None = None
    papersection2totaltestitems: str | None = None
    papersection3numberofattempteditems: str | None = None
    papersection3totaltestitems: str | None = None
    papersection4numberofattempteditems: str | None = None
    papersection4totaltestitems: str | None = None
    paperunit1totaltestitems: str | None = None
    parccstudentidentifier: str | None = None
    percentofitemsattempted: str | None = None
    period: str | None = None
    primarydisabilitytype: str | None = None
    refreshablebrailledisplay: str | None = None
    refreshablebrailledisplayforelal: str | None = None
    reportsuppressionaction: str | None = None
    reportsuppressioncode: str | None = None
    responsibleaccountabledistrictcode: str | None = None
    responsibleaccountableschoolcode: str | None = None
    responsibledistrictcode: str | None = None
    responsibledistrictname: str | None = None
    responsibleorganizationaltype: str | None = None
    responsibleorganizationcodetype: str | None = None
    responsibleschoolcode: str | None = None
    responsibleschoolname: str | None = None
    retest: str | None = None
    rosterflag: str | None = None
    separatealternatelocation: str | None = None
    sex: str | None = None
    shipreportdistrictcode: str | None = None
    shipreportschoolcode: str | None = None
    smallgrouptesting: str | None = None
    smalltestinggroup: str | None = None
    spanishtransadaptation: str | None = None
    spanishtransadaptationofthemathematicsassessment: str | None = None
    specialeducationplacement: str | None = None
    specializedequipmentorfurniture: str | None = None
    specifiedareaorsetting: str | None = None
    speechtotextandwordprediction: str | None = None
    staffmemberidentifier: str | None = None
    stateabbreviation: str | None = None
    statefield1: str | None = None
    statefield10: str | None = None
    statefield11: str | None = None
    statefield12: str | None = None
    statefield13: str | None = None
    statefield14: str | None = None
    statefield15: str | None = None
    statefield2: str | None = None
    statefield3: str | None = None
    statefield4: str | None = None
    statefield5: str | None = None
    statefield6: str | None = None
    statefield7: str | None = None
    statefield8: str | None = None
    statefield9: str | None = None
    statestudentidentifier: str | None = None
    studentassessmentidentifier: str | None = None
    studentreadsassessmentaloudtoself: str | None = None
    studentreadsassessmentaloudtothemselves: str | None = None
    studenttestuuid: str | None = None
    studentunit1testuuid: str | None = None
    studentunit2testuuid: str | None = None
    studentunit3testuuid: str | None = None
    studentunit4testuuid: str | None = None
    studentuuid: str | None = None
    studentwithdisabilities: str | None = None
    subclaim1category: str | None = None
    subclaim1categoryifnotattempted: str | None = None
    subclaim2category: str | None = None
    subclaim2categoryifnotattempted: str | None = None
    subclaim3category: str | None = None
    subclaim3categoryifnotattempted: str | None = None
    subclaim4category: str | None = None
    subclaim4categoryifnotattempted: str | None = None
    subclaim5category: str | None = None
    subclaim5categoryifnotattempted: str | None = None
    subclaim6category: str | None = None
    subject: str | None = None
    summativeflag: str | None = None
    testadministration: str | None = None
    testadministrator: str | None = None
    testattemptednessflag: str | None = None
    testcode: str | None = None
    testcsemprobablerange: str | None = None
    testcsemprobablerangeifnotattempted: str | None = None
    testingdistrictcode: str | None = None
    testingdistrictname: str | None = None
    testingorganizationaltype: str | None = None
    testingschoolcode: str | None = None
    testingschoolname: str | None = None
    testperformancelevel: str | None = None
    testperformancelevelifnotattempted: str | None = None
    testreadingcsem: str | None = None
    testreadingcsemifnotattempted: str | None = None
    testreadingscalescore: str | None = None
    testreadingscalescoreifnotattempted: str | None = None
    testscalescore: str | None = None
    testscalescoreifnotattempted: str | None = None
    testscorecomplete: str | None = None
    teststatus: str | None = None
    testwritingcsem: str | None = None
    testwritingcsemifnotattempted: str | None = None
    testwritingscalescore: str | None = None
    testwritingscalescoreifnotattempted: str | None = None
    texttospeech: str | None = None
    timeofday: str | None = None
    titleiiilimitedenglishproficientparticipationstatus: str | None = None
    totaltestitems: str | None = None
    totaltestitemsattempted: str | None = None
    translationofthemathematicsassessment: str | None = None
    twoormoreraces: str | None = None
    uniqueaccommodation: str | None = None
    unit1formid: str | None = None
    unit1numberofattempteditems: str | None = None
    unit1onlinetestenddatetime: str | None = None
    unit1onlineteststartdatetime: str | None = None
    unit1totaltestitems: str | None = None
    unit2formid: str | None = None
    unit2numberofattempteditems: str | None = None
    unit2onlinetestenddatetime: str | None = None
    unit2onlineteststartdatetime: str | None = None
    unit2totaltestitems: str | None = None
    unit3formid: str | None = None
    unit3numberofattempteditems: str | None = None
    unit3onlinetestenddatetime: str | None = None
    unit3onlineteststartdatetime: str | None = None
    unit3totaltestitems: str | None = None
    unit4formid: str | None = None
    unit4numberofattempteditems: str | None = None
    unit4onlinetestenddatetime: str | None = None
    unit4onlineteststartdatetime: str | None = None
    unit4totaltestitems: str | None = None
    voidscorecode: str | None = None
    voidscorereason: str | None = None
    white: str | None = None
    wordprediction: str | None = None
    wordpredictionforelal: str | None = None
    wordtoworddictionaryenglishnativelanguage: str | None = None

    filler: str | None = FILLER_FIELD


class NJSLA(BaseModel):
    accountabledistrictcode: str | None = None
    accountabledistrictname: str | None = None
    accountableorganizationaltype: str | None = None
    accountableschoolcode: str | None = None
    accountableschoolname: str | None = None
    administrationdirectionsclarifiedinstudentsnativelanguage: str | None = None
    administrationdirectionsreadaloudinstudentsnativelanguage: str | None = None
    alternaterepresentationpapertest: str | None = None
    americanindianoralaskanative: str | None = None
    answermasking: str | None = None
    answersrecordedintest_booklet: str | None = None
    answersrecordedintestbooklet: str | None = None
    asian: str | None = None
    aslvideo: str | None = None
    assessmentgrade: str | None = None
    assessmentyear: str | None = None
    assistivetechnologynonscreenreader: str | None = None
    assistivetechnologyscreenreader: str | None = None
    batteryformid: str | None = None
    birthdate: str | None = None
    blackorafricanamerican: str | None = None
    braillewithtactilegraphics: str | None = None
    calculationdeviceandmathematicstools: str | None = None
    claimcode: str | None = None
    classname: str | None = None
    closedcaptioningforela: str | None = None
    closedcaptioningforelal: str | None = None
    colorcontrast: str | None = None
    critiquingpracticesperformancelevel: str | None = None
    datefirstenrolledinusschool: str | None = None
    earthandspacescienceperformancelevel: str | None = None
    economicdisadvantagestatus: str | None = None
    elaccommodation: str | None = None
    elaconstructedresponse: str | None = None
    elalconstructedresponse: str | None = None
    elalselectedresponseortechnologyenhanceditems: str | None = None
    elaselectedresponseortechnologyenhanceditems: str | None = None
    electronicbrailleresponse: str | None = None
    elexemptfromtakingela: str | None = None
    elexemptfromtakingelal: str | None = None
    emergencyaccommodation: str | None = None
    englishlearneraccommodatedresponses: str | None = None
    englishlearnerel: str | None = None
    extendedtime: str | None = None
    federalraceethnicity: str | None = None
    first_high_school_math_assessment: str | None = None
    firsthighschoolmathassessment: str | None = None
    firstname: str | None = None
    formeriep: str | None = None
    formid: str | None = None
    frequentbreaks: str | None = None
    gender: str | None = None
    gradelevelwhenassessed: str | None = None
    hispanicorlatinoethnicity: str | None = None
    home_language: str | None = None
    homelanguage: str | None = None
    homeless: str | None = None
    homelessprimarynighttimeresidence: str | None = None
    humanreaderorhumansigner: str | None = None
    humansignerfortestdirections: str | None = None
    iepexemptfrompassing: str | None = None
    investigatingpracticesperformancelevel: str | None = None
    languagecode: str | None = None
    largeprint: str | None = None
    lastorsurname: str | None = None
    lifescienceperformancelevel: str | None = None
    localstudentidentifier: str | None = None
    mathematics_scienceaccommodatedresponse: str | None = None
    mathematicsscienceaccommodatedresponse: str | None = None
    middlename: str | None = None
    migrantstatus: str | None = None
    mlaccommodation: str | None = None
    mlexemptfromtakingela: str | None = None
    monitortestresponse: str | None = None
    multilinguallearneraccommodatedresponses: str | None = None
    multilinguallearnerml: str | None = None
    multipletestregistration: str | None = None
    nativehawaiianorotherpacificislander: str | None = None
    njelstatus: str | None = None
    njmlstatus: str | None = None
    njnotattemptflag: str | None = None
    nottestedcode: str | None = None
    nottestedreason: str | None = None
    onlinepcr1: str | None = None
    onlinepcr2: str | None = None
    paperattemptcreatedate: str | None = None
    paperformid: str | None = None
    paperpcr1: str | None = None
    paperpcr2: str | None = None
    papersection1numberofattempteditems: str | None = None
    papersection1totaltestitems: str | None = None
    papersection2numberofattempteditems: str | None = None
    papersection2totaltestitems: str | None = None
    papersection3numberofattempteditems: str | None = None
    papersection3totaltestitems: str | None = None
    papersection4numberofattempteditems: str | None = None
    papersection4totaltestitems: str | None = None
    percentofitemsattempted: str | None = None
    period: str | None = None
    physicalscienceperformancelevel: str | None = None
    primarydisabilitytype: str | None = None
    refreshablebrailledisplay: str | None = None
    reportsuppressionaction: str | None = None
    reportsuppressioncode: str | None = None
    retest: str | None = None
    rosterflag: str | None = None
    sensemakingpracticesperformancelevel: str | None = None
    separatealternatelocation: str | None = None
    sex: str | None = None
    shipreportdistrictcode: str | None = None
    shipreportschoolcode: str | None = None
    smallgrouptesting: str | None = None
    spanishtransadaptation: str | None = None
    specialeducationplacement: str | None = None
    specializedequipmentorfurniture: str | None = None
    specifiedareaorsetting: str | None = None
    speechtotextandwordprediction: str | None = None
    staffmemberidentifier: str | None = None
    statestudentidentifier: str | None = None
    studentassessmentidentifier: str | None = None
    studentreadsassessmentaloudtoself: str | None = None
    studenttestuuid: str | None = None
    studentunit1testuuid: str | None = None
    studentunit2testuuid: str | None = None
    studentunit3testuuid: str | None = None
    studentuuid: str | None = None
    studentwithdisabilities: str | None = None
    subclaim1category: str | None = None
    subclaim1categoryifnotattempted: str | None = None
    subclaim2category: str | None = None
    subclaim2categoryifnotattempted: str | None = None
    subclaim3category: str | None = None
    subclaim3categoryifnotattempted: str | None = None
    subclaim4category: str | None = None
    subclaim4categoryifnotattempted: str | None = None
    subclaim5category: str | None = None
    subclaim5categoryifnotattempted: str | None = None
    subject: str | None = None
    summativeflag: str | None = None
    testadministration: str | None = None
    testadministrator: str | None = None
    testattemptednessflag: str | None = None
    testcode: str | None = None
    testcsemprobablerange: str | None = None
    testcsemprobablerangeifnotattempted: str | None = None
    testformat: str | None = None
    testingdistrictcode: str | None = None
    testingdistrictname: str | None = None
    testingorganizationaltype: str | None = None
    testingschoolcode: str | None = None
    testingschoolname: str | None = None
    testperformancelevel: str | None = None
    testperformancelevelifnotattempted: str | None = None
    testreadingcsem: str | None = None
    testreadingcsemifnotattempted: str | None = None
    testreadingscalescore: str | None = None
    testreadingscalescoreifnotattempted: str | None = None
    testscalescore: str | None = None
    testscalescoreifnotattempted: str | None = None
    testscorecomplete: str | None = None
    teststatus: str | None = None
    testwritingcsem: str | None = None
    testwritingcsemifnotattempted: str | None = None
    testwritingscalescore: str | None = None
    testwritingscalescoreifnotattempted: str | None = None
    texttospeech: str | None = None
    timeofday: str | None = None
    totaltestitems: str | None = None
    totaltestitemsattempted: str | None = None
    twoormoreraces: str | None = None
    uniqueaccommodation: str | None = None
    unit1formid: str | None = None
    unit1numberofattempteditems: str | None = None
    unit1onlinetestenddatetime: str | None = None
    unit1onlineteststartdatetime: str | None = None
    unit1totaltestitems: str | None = None
    unit2formid: str | None = None
    unit2numberofattempteditems: str | None = None
    unit2onlinetestenddatetime: str | None = None
    unit2onlineteststartdatetime: str | None = None
    unit2totaltestitems: str | None = None
    unit3formid: str | None = None
    unit3numberofattempteditems: str | None = None
    unit3onlinetestenddatetime: str | None = None
    unit3onlineteststartdatetime: str | None = None
    unit3totaltestitems: str | None = None
    unit4onlinetestenddatetime: str | None = None
    unit4onlineteststartdatetime: str | None = None
    voidscorecode: str | None = None
    voidscorereason: str | None = None
    white: str | None = None
    wordprediction: str | None = None
    wordtoworddictionaryenglishnativelanguage: str | None = None

    filler: str | None = FILLER_FIELD


class NJGPA(BaseModel):
    accountabledistrictcode: str | None = None
    accountabledistrictname: str | None = None
    accountableorganizationaltype: str | None = None
    accountableschoolcode: str | None = None
    accountableschoolname: str | None = None
    administrationdirectionsclarifiedinstudentsnativelanguage: str | None = None
    administrationdirectionsreadaloudinstudentsnativelanguage: str | None = None
    alternaterepresentationpapertest: str | None = None
    americanindianoralaskanative: str | None = None
    answermasking: str | None = None
    answersrecordedintestbooklet: str | None = None
    asian: str | None = None
    aslvideo: str | None = None
    assessmentgrade: str | None = None
    assessmentyear: str | None = None
    assistivetechnologynonscreenreader: str | None = None
    assistivetechnologyscreenreader: str | None = None
    batteryformid: str | None = None
    birthdate: str | None = None
    blackorafricanamerican: str | None = None
    braillewithtactilegraphics: str | None = None
    calculationdeviceandmathematicstools: str | None = None
    classname: str | None = None
    closedcaptioningforela: str | None = None
    colorcontrast: str | None = None
    datefirstenrolledinusschool: str | None = None
    economicdisadvantagestatus: str | None = None
    elaccommodation: str | None = None
    elaconstructedresponse: str | None = None
    elaselectedresponseortechnologyenhanceditems: str | None = None
    electronicbrailleresponse: str | None = None
    elexemptfromtakingela: str | None = None
    emergencyaccommodation: str | None = None
    englishlearneraccommodatedresponses: str | None = None
    englishlearnerel: str | None = None
    extendedtime: str | None = None
    federalraceethnicity: str | None = None
    firsthighschoolmathassessment: str | None = None
    firstname: str | None = None
    formeriep: str | None = None
    frequentbreaks: str | None = None
    gender: str | None = None
    gradelevelwhenassessed: str | None = None
    hispanicorlatinoethnicity: str | None = None
    home_language: str | None = None
    homeless_primary_nighttime_residence: str | None = None
    homeless: str | None = None
    homelessprimarynighttimeresidence: str | None = None
    humanreaderorhumansigner: str | None = None
    humansignerfortestdirections: str | None = None
    iepexemptfrompassing: str | None = None
    largeprint: str | None = None
    lastorsurname: str | None = None
    localstudentidentifier: str | None = None
    mathematicsscienceaccommodatedresponse: str | None = None
    middlename: str | None = None
    migrantstatus: str | None = None
    mlaccommodation: str | None = None
    mlexemptfromtakingela: str | None = None
    monitortestresponse: str | None = None
    multilinguallearneraccommodatedresponses: str | None = None
    multilinguallearnerml: str | None = None
    multipletestregistration: str | None = None
    nativehawaiianorotherpacificislander: str | None = None
    njelstatus: str | None = None
    njmlstatus: str | None = None
    njnotattemptflag: str | None = None
    nottestedcode: str | None = None
    nottestedreason: str | None = None
    onlinepcr1: str | None = None
    onlinepcr2: str | None = None
    paperattemptcreatedate: str | None = None
    paperformid: str | None = None
    paperpcr1: str | None = None
    paperpcr2: str | None = None
    papersection1numberofattempteditems: str | None = None
    papersection1totaltestitems: str | None = None
    papersection2numberofattempteditems: str | None = None
    papersection2totaltestitems: str | None = None
    papersection3numberofattempteditems: str | None = None
    papersection3totaltestitems: str | None = None
    papersection4numberofattempteditems: str | None = None
    papersection4totaltestitems: str | None = None
    period: str | None = None
    primarydisabilitytype: str | None = None
    refreshablebrailledisplay: str | None = None
    reportsuppressionaction: str | None = None
    reportsuppressioncode: str | None = None
    retest: str | None = None
    rosterflag: str | None = None
    separatealternatelocation: str | None = None
    shipreportdistrictcode: str | None = None
    shipreportschoolcode: str | None = None
    smallgrouptesting: str | None = None
    spanishtransadaptation: str | None = None
    specialeducationplacement: str | None = None
    specializedequipmentorfurniture: str | None = None
    specifiedareaorsetting: str | None = None
    speechtotextandwordprediction: str | None = None
    staffmemberidentifier: str | None = None
    statestudentidentifier: str | None = None
    studentassessmentidentifier: str | None = None
    studentreadsassessmentaloudtoself: str | None = None
    studenttestuuid: str | None = None
    studentunit1testuuid: str | None = None
    studentunit2testuuid: str | None = None
    studentunit3testuuid: str | None = None
    studentuuid: str | None = None
    studentwithdisabilities: str | None = None
    subclaim1category: str | None = None
    subclaim1categoryifnotattempted: str | None = None
    subclaim2category: str | None = None
    subclaim2categoryifnotattempted: str | None = None
    subclaim3category: str | None = None
    subclaim3categoryifnotattempted: str | None = None
    subclaim4category: str | None = None
    subclaim4categoryifnotattempted: str | None = None
    subclaim5category: str | None = None
    subclaim5categoryifnotattempted: str | None = None
    subject: str | None = None
    summativeflag: str | None = None
    testadministration: str | None = None
    testadministrator: str | None = None
    testattemptednessflag: str | None = None
    testcode: str | None = None
    testcsemprobablerange: str | None = None
    testcsemprobablerangeifnotattempted: str | None = None
    testingdistrictcode: str | None = None
    testingdistrictname: str | None = None
    testingorganizationaltype: str | None = None
    testingschoolcode: str | None = None
    testingschoolname: str | None = None
    testperformancelevel: str | None = None
    testperformancelevelifnotattempted: str | None = None
    testreadingcsem: str | None = None
    testreadingcsemifnotattempted: str | None = None
    testreadingscalescore: str | None = None
    testreadingscalescoreifnotattempted: str | None = None
    testscalescore: str | None = None
    testscalescoreifnotattempted: str | None = None
    testscorecomplete: str | None = None
    teststatus: str | None = None
    testwritingcsem: str | None = None
    testwritingcsemifnotattempted: str | None = None
    testwritingscalescore: str | None = None
    testwritingscalescoreifnotattempted: str | None = None
    texttospeech: str | None = None
    timeofday: str | None = None
    totaltestitems: str | None = None
    totaltestitemsattempted: str | None = None
    twoormoreraces: str | None = None
    uniqueaccommodation: str | None = None
    unit1formid: str | None = None
    unit1numberofattempteditems: str | None = None
    unit1onlinetestenddatetime: str | None = None
    unit1onlineteststartdatetime: str | None = None
    unit1totaltestitems: str | None = None
    unit2formid: str | None = None
    unit2numberofattempteditems: str | None = None
    unit2onlinetestenddatetime: str | None = None
    unit2onlineteststartdatetime: str | None = None
    unit2totaltestitems: str | None = None
    unit3formid: str | None = None
    unit3numberofattempteditems: str | None = None
    unit3onlinetestenddatetime: str | None = None
    unit3onlineteststartdatetime: str | None = None
    unit3totaltestitems: str | None = None
    voidscorecode: str | None = None
    voidscorereason: str | None = None
    white: str | None = None
    wordprediction: str | None = None
    wordtoworddictionaryenglishnativelanguage: str | None = None

    filler: str | None = FILLER_FIELD


class StudentListReport(BaseModel):
    accountable_school: str | None = None
    date_of_birth: str | None = None
    first_name: str | None = None
    last_or_surname: str | None = None
    local_student_identifier: str | None = None
    performance_level: str | None = None
    scale_score: str | None = None
    state_student_identifier: str | None = None
    test_name: str | None = None
    testing_school: str | None = None


class StudentTestUpdate(BaseModel):
    accountable_district_code: str | None = None
    accountable_school_code: str | None = None
    administration_directions_clarified_in_student_s_native_language: str | None = None
    administration_directions_read_aloud_in_student_s_native_language: str | None = None
    alternate_representation_paper_test: str | None = None
    american_indian_or_alaska_native: str | None = None
    answer_masking: str | None = None
    answers_recorded_in_test_booklet: str | None = None
    asian: str | None = None
    asl_video: str | None = None
    assistive_technology_non_screen_reader: str | None = None
    assistive_technology_screen_reader: str | None = None
    birth_date: str | None = None
    black_or_african_american: str | None = None
    braille_with_tactile_graphics: str | None = None
    calculation_device_and_mathematics_tools: str | None = None
    class_name: str | None = None
    closed_captioning_for_ela: str | None = None
    color_contrast: str | None = None
    date_first_enrolled_in_us_school: str | None = None
    economic_disadvantage_status: str | None = None
    ela_constructed_response: str | None = None
    ela_selected_response_or_technology_enhanced_items: str | None = None
    electronic_braille_response: str | None = None
    emergency_accommodation: str | None = None
    extended_time: str | None = None
    federal_race_ethnicity: str | None = None
    first_high_school_math_assessment: str | None = None
    first_name: str | None = None
    former_iep: str | None = None
    frequent_breaks: str | None = None
    gender: str | None = None
    grade_level_when_assessed: str | None = None
    hispanic_or_latino_ethnicity: str | None = None
    home_language: str | None = None
    homeless_primary_nighttime_residence: str | None = None
    homeless: str | None = None
    human_reader_or_human_signer: str | None = None
    human_signer_for_test_directions: str | None = None
    iep_exempt_from_passing: str | None = None
    large_print: str | None = None
    last_or_surname: str | None = None
    local_student_identifier: str | None = None
    mathematics_science_accommodated_response: str | None = None
    middle_name: str | None = None
    migrant_status: str | None = None
    ml_accommodation: str | None = None
    ml_exempt_from_taking_ela: str | None = None
    monitor_test_response: str | None = None
    multilingual_learner_accommodated_response: str | None = None
    multilingual_learner_ml: str | None = None
    multiple_test_registration: str | None = None
    native_hawaiian_or_other_pacific_islander: str | None = None
    nj_ml_status: str | None = None
    not_tested_code: str | None = None
    not_tested_reason: str | None = None
    pas_mi: str | None = None
    primary_disability_type: str | None = None
    refreshable_braille_display: str | None = None
    report_suppression_action: str | None = None
    report_suppression_code: str | None = None
    required_high_school_math_assessment: str | None = None
    retest: str | None = None
    separate_alternate_location: str | None = None
    session_name: str | None = None
    small_group_testing: str | None = None
    spanish_transadaptation: str | None = None
    special_education_placement: str | None = None
    specialized_equipment_or_furniture: str | None = None
    specified_area_or_setting: str | None = None
    speech_to_text_and_word_prediction: str | None = None
    staff_member_identifier: str | None = None
    state_student_identifier: str | None = None
    student_assessment_identifier: str | None = None
    student_reads_assessment_aloud_to_self: str | None = None
    student_test_uuid: str | None = None
    student_uuid: str | None = None
    student_with_disabilities: str | None = None
    test_administration: str | None = None
    test_administrator: str | None = None
    test_code: str | None = None
    test_format: str | None = None
    test_status: str | None = None
    testing_district_code: str | None = None
    testing_school_code: str | None = None
    text_to_speech: str | None = None
    time_of_day: str | None = None
    total_attemptedness_flag: str | None = None
    total_test_items_attempted: str | None = None
    total_test_items: str | None = None
    two_or_more_races: str | None = None
    unique_accommodation: str | None = None
    void_test_score_code: str | None = None
    void_test_score_reason: str | None = None
    white: str | None = None
    word_prediction: str | None = None
    word_to_word_dictionary_english_native_language: str | None = None

    filler: str | None = FILLER_FIELD
