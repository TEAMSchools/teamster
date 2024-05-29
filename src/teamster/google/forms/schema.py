from pydantic import BaseModel


class CorrectAnswer(BaseModel):
    value: str | None = None


class CorrectAnswers(BaseModel):
    answers: list[CorrectAnswer | None] | None = None


class TextLink(BaseModel):
    uri: str | None = None
    displayText: str | None = None


class VideoLink(BaseModel):
    displayText: str | None = None
    youtubeUri: str | None = None


class ExtraMaterial(BaseModel):
    link: TextLink | None = None
    video: VideoLink | None = None


class Feedback(BaseModel):
    text: str | None = None
    material: list[ExtraMaterial | None] | None = None


class QuizSettings(BaseModel):
    isQuiz: bool | None = None


class MediaProperties(BaseModel):
    alignment: str | None = None
    width: int | None = None


class Video(BaseModel):
    youtubeUri: str | None = None
    properties: MediaProperties | None = None


class Image(BaseModel):
    contentUri: str | None = None
    altText: str | None = None
    sourceUri: str | None = None
    properties: MediaProperties | None = None


class Option(BaseModel):
    value: str | None = None
    isOther: bool | None = None
    goToAction: str | None = None
    goToSectionId: str | None = None
    image: Image | None = None


class Columns(BaseModel):
    type: str | None = None
    options: list[Option | None] | None = None


class Grid(BaseModel):
    columns: Columns | None = None


class ChoiceQuestion(BaseModel):
    type: str | None = None
    shuffle: bool | None = None

    options: list[Option | None] | None = None


class Grading(BaseModel):
    pointValue: int | None = None
    correctAnswers: CorrectAnswers | None = None
    whenRight: Feedback | None = None
    whenWrong: Feedback | None = None
    generalFeedback: Feedback | None = None


class DateQuestion(BaseModel):
    includeTime: bool | None = None
    includeYear: bool | None = None


class FileUploadQuestion(BaseModel):
    folderId: str | None = None
    maxFiles: int | None = None
    maxFileSize: str | None = None

    types: list[str | None] | None = None


class RowQuestion(BaseModel):
    title: str | None = None


class ScaleQuestion(BaseModel):
    low: int | None = None
    high: int | None = None
    lowLabel: str | None = None
    highLabel: str | None = None


class TextQuestion(BaseModel):
    paragraph: bool | None = None


class TimeQuestion(BaseModel):
    duration: bool | None = None


class Question(BaseModel):
    questionId: str | None = None
    required: bool | None = None

    choiceQuestion: ChoiceQuestion | None = None
    dateQuestion: DateQuestion | None = None
    fileUploadQuestion: FileUploadQuestion | None = None
    grading: Grading | None = None
    rowQuestion: RowQuestion | None = None
    scaleQuestion: ScaleQuestion | None = None
    textQuestion: TextQuestion | None = None
    timeQuestion: TimeQuestion | None = None


class QuestionGroupItem(BaseModel):
    grid: Grid | None = None
    image: Image | None = None

    questions: list[Question | None] | None = None


class QuestionItem(BaseModel):
    question: Question | None = None
    image: Image | None = None


class ImageItem(BaseModel):
    image: Image | None = None


class VideoItem(BaseModel):
    caption: str | None = None
    video: Video | None = None


class PageBreakItem(BaseModel): ...


class TextItem(BaseModel): ...


class Item(BaseModel):
    itemId: str | None = None
    title: str | None = None
    description: str | None = None

    imageItem: ImageItem | None = None
    pageBreakItem: PageBreakItem | None = None
    questionGroupItem: QuestionGroupItem | None = None
    questionItem: QuestionItem | None = None
    textItem: TextItem | None = None
    videoItem: VideoItem | None = None


class FormSettings(BaseModel):
    quizSettings: QuizSettings | None = None


class Info(BaseModel):
    title: str | None = None
    description: str | None = None
    documentTitle: str | None = None


class Grade(BaseModel):
    score: float | None = None
    correct: bool | None = None
    feedback: Feedback | None = None


class TextAnswer(BaseModel):
    value: str | None = None


class TextAnswers(BaseModel):
    answers: list[TextAnswer | None] | None = None


class FileUploadAnswer(BaseModel):
    fileId: str | None = None
    fileName: str | None = None
    mimeType: str | None = None


class FileUploadAnswers(BaseModel):
    answers: list[FileUploadAnswer | None] | None = None


class Answer(BaseModel):
    questionId: str | None = None

    grade: Grade | None = None
    textAnswers: TextAnswers | None = None
    fileUploadAnswers: FileUploadAnswers | None = None


class Response(BaseModel):
    formId: str | None = None
    responseId: str | None = None
    createTime: str | None = None
    lastSubmittedTime: str | None = None
    respondentEmail: str | None = None
    totalScore: float | None = None

    answers: dict[str, Answer] | None = None


class Form(BaseModel):
    formId: str | None = None
    revisionId: str | None = None
    responderUri: str | None = None
    linkedSheetId: str | None = None

    info: Info | None = None
    settings: FormSettings | None = None

    items: list[Item | None] | None = None
