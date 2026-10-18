class PersonaInfo {
  final String id;
  final String emoji;
  final String displayName;
  final String description;
  final int defaultTriggerRadiusM;

  const PersonaInfo({
    required this.id,
    required this.emoji,
    required this.displayName,
    required this.description,
    required this.defaultTriggerRadiusM,
  });
}

const kPersonas = [
  PersonaInfo(
    id: 'history_uncle',
    emoji: '🏛️',
    displayName: '歷史大叔',
    description: '嚴謹考據，帶你穿越時代脈絡',
    defaultTriggerRadiusM: 100,
  ),
  PersonaInfo(
    id: 'story_brother',
    emoji: '📖',
    displayName: '故事大哥哥',
    description: '鄉野軼事，讓景點活靈活現',
    defaultTriggerRadiusM: 100,
  ),
  PersonaInfo(
    id: 'gossip_auntie',
    emoji: '🗣️',
    displayName: '八卦阿姨',
    description: '名人八卦，讓歷史不再無聊',
    defaultTriggerRadiusM: 100,
  ),
  PersonaInfo(
    id: 'kid_sister',
    emoji: '🌟',
    displayName: '童趣小妹',
    description: '好奇驚嘆，用孩子的眼睛看世界',
    defaultTriggerRadiusM: 100,
  ),
  PersonaInfo(
    id: 'foodie',
    emoji: '🍜',
    displayName: '美食家',
    description: '饕客視角，發掘在地好滋味',
    defaultTriggerRadiusM: 50,
  ),
];
