const videoFiles = [
  ['Backward Fall #1', new URL('../videos/Backward Fall 1_skeleton.mp4', import.meta.url).href],
  ['Backward Fall #2', new URL('../videos/Backward Fall 2_skeleton.mp4', import.meta.url).href],
  ['Forward Fall #1', new URL('../videos/Forward Fall 1_skeleton.mp4', import.meta.url).href],
  ['Forward Fall #2', new URL('../videos/Forward Fall 2_skeleton.mp4', import.meta.url).href],
  ['Recovery #1', new URL('../videos/Recovery 1_skeleton.mp4', import.meta.url).href],
  ['Recovery #2', new URL('../videos/Recovery 2_skeleton.mp4', import.meta.url).href],
  ['Recovery #3', new URL('../videos/Recovery 3_skeleton.mp4', import.meta.url).href],
  ['Recovery #4', new URL('../videos/Recovery 4_skeleton.mp4', import.meta.url).href],
  ['Sideward Fall #1', new URL('../videos/Sideward Fall 1_skeleton.mp4', import.meta.url).href],
  ['Sideward Fall #2', new URL('../videos/Sideward Fall 2_skeleton.mp4', import.meta.url).href],
  ['Sideward Fall #3', new URL('../videos/Sideward Fall 3_skeleton.mp4', import.meta.url).href],
  ['Tripping Fall', new URL('../videos/Tripping Fall_skeleton.mp4', import.meta.url).href],
] as const;

function categoryFromTitle(title: string) {
  if (title.toLowerCase().includes('recovery')) return 'Recovery';
  if (title.toLowerCase().includes('forward')) return 'Forward fall';
  if (title.toLowerCase().includes('backward')) return 'Backward fall';
  if (title.toLowerCase().includes('sideward')) return 'Sideward fall';
  if (title.toLowerCase().includes('tripping')) return 'Tripping';
  return 'Training';
}

function summaryFromTitle(title: string) {
  const category = categoryFromTitle(title).toLowerCase();
  return `Watch the skeleton-guided ${category} example and practice the movement slowly with supervision.`;
}

export const trainingVideos = videoFiles
  .map(([title, source], index) => {
    return {
      id: String(index + 1),
      title,
      duration: 'Video',
      level: 'Demo',
      category: categoryFromTitle(title),
      summary: summaryFromTitle(title),
      source: source as string,
    };
  });

export const practiceFeedback = {
  riskScore: 28,
  headline: "Low risk in today's session",
  note: 'Your posture stayed steady. Try slowing down the final step for even more control.',
  suggestions: [
    'Keep feet slightly wider during turns.',
    'Pause for one breath before standing.',
    'Practice the chair rise drill tomorrow.',
  ],
};

export const progressStats = [
  { label: 'Sessions this week', value: '4' },
  { label: 'Practice streak', value: '6 days' },
  { label: 'Completed lessons', value: '12' },
];
