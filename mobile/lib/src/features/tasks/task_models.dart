class Project {
  const Project({required this.id, required this.workspaceId, required this.name, required this.key, required this.status, this.dueDate});
  final String id;
  final String workspaceId;
  final String name;
  final String key;
  final String status;
  final String? dueDate;

  factory Project.fromJson(Map<String, dynamic> json) => Project(
        id: json['id'] as String,
        workspaceId: json['workspace_id'] as String,
        name: json['name'] as String,
        key: json['key'] as String,
        status: json['status'] as String,
        dueDate: json['due_date'] as String?,
      );
  Map<String, dynamic> toJson() => {'id': id, 'workspace_id': workspaceId, 'name': name, 'key': key, 'status': status, 'due_date': dueDate};
}

class BoardColumn {
  const BoardColumn({required this.id, required this.projectId, required this.name, required this.position});
  final String id;
  final String projectId;
  final String name;
  final int position;
  factory BoardColumn.fromJson(Map<String, dynamic> json) => BoardColumn(id: json['id'] as String, projectId: json['project_id'] as String, name: json['name'] as String, position: json['position'] as int);
  Map<String, dynamic> toJson() => {'id': id, 'project_id': projectId, 'name': name, 'position': position};
}

class TaskItem {
  const TaskItem({required this.id, required this.workspaceId, required this.projectId, required this.columnId, required this.identifier, required this.title, required this.description, required this.priority, required this.status, required this.position, required this.version, required this.createdAt, required this.updatedAt, this.dueDate});
  final String id;
  final String workspaceId;
  final String projectId;
  final String columnId;
  final String identifier;
  final String title;
  final String description;
  final String priority;
  final String status;
  final double position;
  final int version;
  final String? dueDate;
  final String createdAt;
  final String updatedAt;

  TaskItem copyWith({String? columnId,String? title,String? description,String? priority,String? status,double? position,int? version,String? dueDate,bool clearDueDate=false,String? updatedAt}) => TaskItem(
        id:id,
        workspaceId:workspaceId,
        projectId:projectId,
        columnId:columnId??this.columnId,
        identifier:identifier,
        title:title??this.title,
        description:description??this.description,
        priority:priority??this.priority,
        status:status??this.status,
        position:position??this.position,
        version:version??this.version,
        dueDate:clearDueDate?null:dueDate??this.dueDate,
        createdAt:createdAt,
        updatedAt:updatedAt??this.updatedAt,
      );

  factory TaskItem.fromJson(Map<String, dynamic> json) => TaskItem(
        id: json['id'] as String,
        workspaceId: json['workspace_id'] as String,
        projectId: json['project_id'] as String,
        columnId: json['column_id'] as String,
        identifier: json['identifier'] as String,
        title: json['title'] as String,
        description: (json['description'] as String?) ?? '',
        priority: json['priority'] as String,
        status: json['status'] as String,
        position: (json['position'] as num).toDouble(),
        version: json['version'] as int,
        dueDate: json['due_date'] as String?,
        createdAt: json['created_at'] as String,
        updatedAt: json['updated_at'] as String,
      );
  Map<String, dynamic> toJson() => {'id': id, 'workspace_id': workspaceId, 'project_id': projectId, 'column_id': columnId, 'identifier': identifier, 'title': title, 'description': description, 'priority': priority, 'status': status, 'position': position, 'version': version, 'due_date': dueDate, 'created_at': createdAt, 'updated_at': updatedAt};
}

class BoardData {
  const BoardData({required this.project, required this.columns, required this.tasks});
  final Project project;
  final List<BoardColumn> columns;
  final List<TaskItem> tasks;
  factory BoardData.fromJson(Map<String, dynamic> json) => BoardData(
        project: Project.fromJson((json['project'] as Map).cast<String, dynamic>()),
        columns: (json['columns'] as List).map((item) => BoardColumn.fromJson((item as Map).cast<String, dynamic>())).toList(),
        tasks: (json['tasks'] as List).map((item) => TaskItem.fromJson((item as Map).cast<String, dynamic>())).toList(),
      );
  Map<String, dynamic> toJson() => {'project': project.toJson(), 'columns': columns.map((item) => item.toJson()).toList(), 'tasks': tasks.map((item) => item.toJson()).toList()};
}

class CommentItem {
  const CommentItem({required this.id, required this.taskId, required this.authorId, required this.body, required this.createdAt, this.editedAt});
  final String id;
  final String taskId;
  final String authorId;
  final String body;
  final String createdAt;
  final String? editedAt;
  factory CommentItem.fromJson(Map<String, dynamic> json) => CommentItem(
        id: json['id'] as String,
        taskId: json['task_id'] as String,
        authorId: json['author_id'] as String,
        body: json['body'] as String,
        editedAt: json['edited_at'] as String?,
        createdAt: json['created_at'] as String,
      );
}

class NotificationItem {
  const NotificationItem({required this.id, required this.kind, required this.title, required this.body, required this.createdAt, this.entityType, this.entityId, this.readAt});
  final String id;
  final String kind;
  final String title;
  final String body;
  final String? entityType;
  final String? entityId;
  final String? readAt;
  final String createdAt;
  factory NotificationItem.fromJson(Map<String, dynamic> json) => NotificationItem(id: json['id'] as String, kind: json['kind'] as String, title: json['title'] as String, body: (json['body'] as String?) ?? '', entityType: json['entity_type'] as String?, entityId: json['entity_id'] as String?, readAt: json['read_at'] as String?, createdAt: json['created_at'] as String);
}
